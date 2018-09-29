from flask import Flask, render_template, request, redirect, session, url_for, g, Response, stream_with_context
import config
from exts import db
from decorators import login_required
from gevent import monkey
import sys
from os.path import basename, realpath
from gevent.pywsgi import WSGIServer
from license_handle import LicServer, LicClient
from models import LicenseClientModel
from sqlalchemy import or_
from utils import get_logger, file_stream
import re


monkey.patch_all()

app = Flask(__name__)
app.config.from_object(config)
db.init_app(app)

LOGGER = get_logger(basename((realpath(__file__))))


@app.route('/')
@login_required
def index():
    context = {
        'clients': LicenseClientModel.query.all()
    }
    return render_template('index.html', **context)


@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        username = request.form.get('username')
        password = request.form.get('password')
        if username != config.USER or password != config.PWD:
            return u'username or password error'
        else:
            session['user'] = username
            g.user = username

            return redirect(url_for('index'))


@login_required
@app.route('/detail/<int:client_id>')
def detail(client_id):
    client_model = LicenseClientModel.query.get(client_id)
    return render_template('detail.html', client=client_model)


@app.route('/search/')
@login_required
def search():
    keyword = request.args.get('k')
    LOGGER.debug('search string is ' + keyword)
    clients = LicenseClientModel.query.filter(or_(LicenseClientModel.sn.contains(keyword),
                                                  LicenseClientModel.cardtype.contains(keyword)))
    context = {
        'clients': clients
    }
    return render_template('index.html', **context)


@app.route('/logout/')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/license/req/', methods=['POST'])
def license_req():
    if request.method == 'POST':
        licReqInfo = request.form.to_dict()
        for k,v in licReqInfo.items():
            LOGGER.debug('%s: %s' % (k, v))
        if licServerIns.configLoaded == False:
            licServerIns.loadConfig()

        global licClientIns
        licClientIns = LicClient(licServerIns)
        licResult = licClientIns.licGen(licReqInfo, 'remote')

        # return license result(json) to user
        return licResult

    else:
        return u'Unsupported request!'


@app.route('/generate/', methods=['GET', 'POST'])
@login_required
def generate():
    if request.method == 'GET':
        return render_template('generate.html')
    else:
        card_list = request.form.getlist('card')
        sn_list = request.form.getlist('sn')
        mac_list = request.form.getlist('mac')

        #convert to upper
        card_list = list(map(lambda x:x.upper(), card_list))

        # convert list to dict
        licClientlist = []
        licClientDic = {}

        for i in range(len(card_list)):
            licClientDic['cardtype'] = card_list[i]
            licClientDic['SN'] = sn_list[i]
            licClientDic['MAC'] = mac_list[i]
            licClientlist.append(licClientDic)
            licClientDic = {}

        LOGGER.debug(licClientlist)

        #check card type, SN and MAC address
        E7_CARD_LIST = ['NGPON2X4', 'GPON8R2', '10GE-12', 'GE-24']
        reSN = re.compile(r'\d{12}')
        reMAC = re.compile(r'^([0-9a-fA-F]{2}[:]){5}([0-9a-fA-F]{2})')
        for el in licClientlist:
            if el['cardtype'] not in E7_CARD_LIST or re.match(reSN, el['SN']) is None or re.match(reMAC,
                                                                                                  el['MAC']) is None:
                licClientlist.remove(el)

        LOGGER.debug(licClientlist)

        if licServerIns.configLoaded == False:
            licServerIns.loadConfig()

        for el in licClientlist:
            licClientObj = LicClient(licServerIns)
            licClientObj.licGen(el, 'local')
            licClientObj.close()

        return redirect(url_for('index'))


@app.route('/license/download/')
def license_download():
    filename = request.args.get('filename')

    licClientIns.licUpdateStatus(filename, 'ACTIVATING')

    return Response(stream_with_context(file_stream(sys.path[0] + '/static/keydir/' + filename)),
                     content_type='application/octet-stream',
                     direct_passthrough=True)


@app.route('/license/download/<filename>')
def license_download_byname(filename):
    LOGGER.debug('filename is %s' + filename)
    if 'dat' in filename:
        return Response(stream_with_context(file_stream(sys.path[0] + '/static/keydir/' + filename)),
                    content_type='application/octet-stream',
                    direct_passthrough=True)
    elif 'png' in filename:
        return Response(stream_with_context(file_stream(sys.path[0] + '/static/qrdir/' + filename)),
                    content_type='application/octet-stream',
                    direct_passthrough=True)
    else:
        return u'No such file!'


@app.route('/license/status/', methods=['GET', 'POST'])
def license_status():
    if request.method == 'GET':
        pass
    else:
        status = request.form.get('status')
        filename = request.form.get('filename')

        if status == 'OK':
            status = 'ACTIVATED'
        else:
            status = 'UNACTIVATED'

        LOGGER.debug('status is ' + filename)

        licClientIns.licUpdateStatus(filename, status)

        licClientIns.close()

        return u''


@app.before_request
def before_request():
    g.user = session.get('user')


@app.context_processor
def my_context_processor():

    if hasattr(g, 'user'):
        return {'user': g.user}
    else:
        return {}

def main():
    try:
        global licServerIns
        licServerIns = LicServer()

        LOGGER.debug('Start server')
        server = WSGIServer(('0.0.0.0', 9000,), app)

        server.serve_forever()

    except KeyboardInterrupt:
        pass

    return 0


if __name__ == '__main__':
    sys.exit(main())
