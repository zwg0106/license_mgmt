import sys
import os
import libnacl
import libnacl.dual
import base64
import hashlib
import configparser
import json
from datetime import datetime, timedelta
import config
from exts import db
from models import LicenseServerModel, LicenseClientModel
import qrcode
from utils import get_logger
from os.path import basename, realpath

LOGGER = get_logger(basename((realpath(__file__))))

class LicServer(object):
    """ licesne server class"""

    def __init__(self):
        self.idKey = ''
        self.baseKey = ''
        self.licS = {}
        self.payLoadD = {}
        self.licMaxNum = ''
        self.licAvlNum = 0
        self.deadLine = 0
        self.serverID = {}
        self.configLoaded = False


    def loadConfig(self):
        self.licS = {}
        self.licS['status'] = 'INIT'
        configObj = configparser.ConfigParser()
        configObj.read(sys.path[0] + '/' + config.LIC_CONFIG_FILE)
        self.licS['Product'] = configObj.get('main', 'Product')
        self.licS['Owner'] = configObj.get('main', 'Owner')
        self.licS['CustomerName'] = configObj.get('main', 'CustomerName')
        self.payLoadD['Feature1'] = configObj.get('payload', 'feature1')
        self.payLoadD['Feature2'] = configObj.get('payload', 'feature2')
        self.payLoadD['Feature3'] = configObj.get('payload', 'feature3')
        self.payLoadD['Feature4'] = configObj.get('payload', 'feature4')
        self.payLoadD['Feature5'] = configObj.get('payload', 'feature5')
        self.payLoadD['Feature6'] = configObj.get('payload', 'feature6')
        self.licS['Feature'] = self.payLoadD

        self.licMaxNum = configObj.get('main', 'UserCount')
        self.licAvlNum = int(self.licMaxNum)
        self.deadLine = configObj.get('main', 'Deadline')

        for k, v in self.licS.items():
            LOGGER.debug('licS: %s : %s' % (k, v))

        serverModel = LicenseServerModel.query.filter_by(customer_name=self.licS['CustomerName'],
                                                         product=self.licS['Product']).first()
        if serverModel:
            self.serverID = serverModel
        else:
            licServerD = LicenseServerModel(customer_name=self.licS['CustomerName'], owner=self.licS['Owner'],
                                            product=self.licS['Product'], maxusercount=int(self.licMaxNum),
                                            availusercount=int(self.licMaxNum))

            db.session.add(licServerD)
            db.session.commit()

            serverModel = LicenseServerModel.query.filter_by(customer_name=self.licS['CustomerName'],
                                                             product=self.licS['Product']).first()
            if serverModel:
                self.serverID = serverModel
            else:
                LOGGER.error('No product searched in DB')

        self.configLoaded = True


class LicClient(object):
    def __init__(self, server):
        self._server = server
        self.licD = {}


    def licGenMetaData(self):
        sortFeatureD = []

        for k in sorted(self.licD['Feature'].keys()):
            sortFeatureD.append((k, self.licD['Feature'][k]))
        self.licD['Feature'] = sortFeatureD

        # lower key
        tmplicD = {k.lower(): v for k, v in self.licD.items()}
        tmplicD.pop('status')
        tmplicD.pop('product')
        sortLicD = [(k, tmplicD[k]) for k in sorted(tmplicD.keys())]

        LOGGER.debug('sortLicD: %s' % sortLicD)
        id_str = json.dumps(sortLicD)
        LOGGER.debug('id_str: %s ' % id_str)
        self.licD['id'] = hashlib.md5(id_str.encode('utf-8')).hexdigest()
        LOGGER.debug('lic id is %s' % self.licD['id'])


    def licCreateKeyFile(self):
        baseKeyFile = sys.path[0] + '/' + config.LIC_KEY_PATH + '/' + 'base.key'
        if os.path.isfile(baseKeyFile) is not True:
            baseKey = libnacl.dual.DualSecret()
            LOGGER.debug('baseKeyFile is %s' + baseKeyFile)
            baseKey.save(baseKeyFile)

        idKeyFile = sys.path[0] + '/' + config.LIC_KEY_PATH + '/' + 'id.key'
        if os.path.isfile(idKeyFile) is not True:
            idKey = libnacl.dual.DualSecret()
            LOGGER.debug('idKeyFile is %s' + idKeyFile)
            idKey.save(idKeyFile)

        self.baseKey = baseKeyFile
        self.idKey = idKeyFile


    def encryptLicId(self):
        baseKey = libnacl.utils.load_key(self.baseKey)
        idKey = libnacl.utils.load_key(self.idKey)
        idBox = libnacl.public.Box(baseKey.sk, idKey.pk)
        idEncr = idBox.encrypt(bytes(self.licD['id'], 'utf-8'))
        idB64Ctxt = base64.urlsafe_b64encode(idEncr)
        self.licD['key'] = idB64Ctxt.decode('utf-8')
        LOGGER.debug('idB64Ctxt is %s key is %s' % (idB64Ctxt, self.licD['key']))

        self.licD['Issued_time'] = datetime.now().replace(microsecond=0)
        self.licD['Expired_time'] = self.licD['Issued_time'] + timedelta(days=int(self._server.deadLine))

        self.licD['licFile'] = 'license_{}.dat'.format(self.licD['SN'])

        featureInfo = 'Feature1:{}  Feature2:{}  Feature3:{}  Feature4:{}  Feature5:{}  Feature6:{}'.format(
            self.licD['Feature'][0][1], self.licD['Feature'][1][1], self.licD['Feature'][2][1],
            self.licD['Feature'][3][1], self.licD['Feature'][4][1], self.licD['Feature'][5][1])

        licInfo = 'SN:{}  CARDTYPE:{}  OWNER:{}  MAC:{}  CUSTOMERNAME:{}  ISSUED:{}  EXPIRED:{}  FEATURE:{}'.format(
            self.licD['SN'], self.licD['cardtype'], self.licD['Owner'], self.licD['MAC'], self.licD['CustomerName'],
            self.licD['Issued_time'], self.licD['Expired_time'], featureInfo)

        licKey = 'KEY:{}'.format(self.licD['key'])

        licFileName = sys.path[0] + '/static/keydir/' + self.licD['licFile']
        with open(licFileName, 'w') as licFile:
            licFile.write(licInfo)
            licFile.write('  ')
            licFile.write(licKey)

        self.licD['filesize'] = os.path.getsize(licFileName)


    def genQrFile(self):
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4, )
        qr.add_data(self.licD)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        # save
        self.licD['qrFile'] = 'license_{}.png'.format(self.licD['SN'])
        img.save(sys.path[0] + '/static/qrdir/' + self.licD['qrFile'])


    def licGen(self, lic_info, mode):
    # mode is local or remote

        self.licD = dict(self.licD, **lic_info)
        self.licD = dict(self.licD, **self._server.licS)

        self.licGenMetaData()

        self.licCreateKeyFile()

        self.licCreateKeyFile()

        self.encryptLicId()

        self.genQrFile()

        licFileData = {'licFilename': self.licD['licFile'], 'licFilesize': self.licD['filesize']}

        self.licD['status'] = 'GENERATED'

        clientModel = LicenseClientModel.query.filter_by(sn=self.licD['SN']).first()
        if clientModel is None:
            clientModel = LicenseClientModel(cardtype=self.licD['cardtype'], sn=self.licD['SN'],
                                             mac_addr=self.licD['MAC'],
                                             status=self.licD['status'], issued_time=self.licD['Issued_time'],
                                             expired_time=self.licD['Expired_time'], filename=self.licD['licFile'],
                                             filesize=self.licD['filesize'], qrfile=self.licD['qrFile'])

            clientModel.server = self._server.serverID

            db.session.add(clientModel)
            db.session.commit()
        else:
            pass

        # send base.pk to user to decode license file
        licFileData['pk'] = base64.urlsafe_b64encode(libnacl.utils.load_key(self.baseKey).hex_pk()).decode()
        LOGGER.debug('pk is %s' + licFileData['pk'])

        if mode == 'remote':
            return json.dumps(licFileData)
        else:
            pass


    def licUpdateStatus(self, file, Str):
        self.licD['status'] = Str
        db.session.query(LicenseClientModel).filter_by(filename=file).update(
            {LicenseClientModel.status: self.licD['status']})
        db.session.commit()
        if self.licD['status'] == 'ACTIVATED':
            self._server.licAvlNum -= 1


    def close(self):
        self.licD = {}
        self._server = ''
        LOGGER.debug('license client object is closed')