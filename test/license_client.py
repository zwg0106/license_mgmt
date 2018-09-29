import os
import sys
import re
from urllib import request, parse
import json
import argparse
import base64
import datetime
import hashlib
import libnacl
import libnacl.dual

id_priv_key = 'aa83e4f1f7e3f9c8852e3640d9a11e1cb6e1f5e9f17f5c7a5514a0cbc6708e71'

def get_arguments():
    """Get parsed passed in arguments."""
    parser = argparse.ArgumentParser(description="license client arguments")
    parser.add_argument('-s', '--serialnumber', type=str, required=True, help='Specify serial number')
    parser.add_argument('-m', '--macaddress', type=str, required=True, help='Specify MAC address')
    parser.add_argument('-c', '--cardtype', type=str, required=True, help='Specify Card type')

    arguments = parser.parse_args()

    return arguments


def get_license_file(args):
	
	if args.serialnumber and args.macaddress and args.cardtype is None:
		print('invalid paramter. please specify \'%s -s -m -c\'' % sys.argv[0])
		return

	license_client = {}
	license_client['SN'] = args.serialnumber                                                                                                                    
	license_client['MAC'] = args.macaddress                             
	license_client['cardtype'] = args.cardtype
    
	format_data = parse.urlencode(license_client).encode('utf-8')                           
    
	print('format data is %s' % format_data)

	req = request.Request('http://127.0.0.1:9000/license/req/', format_data)

    # get license file, size and server public key
	resp = request.urlopen(req)

	content = json.loads(resp.read().decode('utf-8'))

	print('filename is %s size is %s public key is %s' % (content['licFilename'], content['licFilesize'], content['pk']))

	pk = base64.urlsafe_b64decode(content['pk'].encode(encoding='utf-8').decode())

	license_client['pk'] = pk
	
	print('pk is %s' % pk)

	params = parse.urlencode({'filename': content['licFilename']})
    
	print('params %s' % params)

	req = request.Request('http://127.0.0.1:9000/license/download?' + params)
        
	with request.urlopen(req) as f:
		data = f.read()
		print('Status:', f.status, f.reason)
            
		for k,v in f.getheaders():
			print('%s: %s' % (k,v))
        
	with open(content['licFilename'], 'wb') as fw:
		fw.write(data)
    
	# verify file size
	if os.path.getsize(content['licFilename']) != content['licFilesize']:
		print('file size not matched')
		return {}

	license_client['filename'] = content['licFilename']

	return license_client
 

def parse_lic_file(lic_client_d):
    if lic_client_d['filename'] is not None:
        with open(lic_client_d['filename'], 'r') as lic_file:
            lic_bytes = lic_file.read()

    # get MAC address
    mac_address = re.search(r'MAC:([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})', lic_bytes, re.I).group()
    print('mac_address is before: %s' % mac_address)
    mac_address = '{}:{}:{}:{}:{}:{}'.format(*(mac_address.split(":")[1:]))
    print('mac_address is after: %s' % mac_address)

    # get issued and expired time
    issued_time= re.search(r'ISSUED:\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}', lic_bytes, re.I).group()
    issued_time = re.sub(r'ISSUED:', '', issued_time)

    expired_time= re.search(r'EXPIRED:\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}', lic_bytes, re.I).group()
    expired_time = re.sub(r'EXPIRED:', '', expired_time)

    # get Feature
    feature_info = re.search(r'FEATURE:(Feature\d:(true|false)\s{2}){5}(Feature\d:(true|false))', lic_bytes, re.I).group()
    feature_info = re.sub(r'FEATURE:', '', feature_info)
    print(feature_info)

    feature_dict = dict([(x.split(":")[0], x.split(":")[1]) for x in feature_info.split("  ")])
    print(feature_dict)

    # remove mac, issued, expired time and feature from dict
    lic_bytes = re.sub(r'MAC:([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})\s{2}', '', lic_bytes)
    lic_bytes = re.sub(r'ISSUED:\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\s{2}', '', lic_bytes)
    lic_bytes = re.sub(r'EXPIRED:\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\s{2}', '', lic_bytes)
    lic_bytes = re.sub(r'FEATURE:(Feature\d:(true|false)\s{2}){6}', '', lic_bytes)

    print("lic_bytes is %s" % lic_bytes)
    licDict = dict([(x.split(":")[0], x.split(":")[1]) for x in lic_bytes.split("  ")])

    print("licDict is %s" % licDict)

    licDict['FEATURE'] = feature_dict 
    licDict['MAC'] = mac_address

    issueDate = datetime.datetime.strptime(issued_time, "%Y-%m-%d %H:%M:%S")
    expiredDate = datetime.datetime.strptime(expired_time, "%Y-%m-%d %H:%M:%S")

    if licDict['SN'] != lic_client_d['SN'] or licDict['MAC'] != lic_client_d['MAC'] or licDict['CARDTYPE'] != lic_client_d['cardtype']:
        print('license file is not matched')

    licDict['ISSUED'] = issueDate 
    licDict['EXPIRED'] = expiredDate

    #licDict['mac'] = licDict['mac'].replace('-',':')
    licDict['pk'] = lic_client_d['pk']
	
    print('licDict is %s' % licDict)

    return licDict

 
def verify_lic(licD):
    
    key = licD['KEY']
    issueDate = licD['ISSUED']
    expiresDate = licD['EXPIRED']
    pk = licD['pk']

    licD.pop('pk')
    licD.pop('KEY')
    licD.pop('ISSUED')
    licD.pop('EXPIRED')

    sortFeatureD = [(k,licD['FEATURE'][k]) for k in sorted(licD['FEATURE'].keys())]
    licD.pop('FEATURE')
    licD['Feature'] = sortFeatureD

    # lower key
    tmplicD = {k.lower(): v for k, v in licD.items()}

    sortLicD = [(k,tmplicD[k]) for k in sorted(tmplicD.keys())]
    print('sortLicD is %s ' % sortLicD)
    id_str = json.dumps(sortLicD)
    print('id_str is %s ' % id_str)
    licD['id'] = hashlib.md5(id_str.encode('utf-8')).hexdigest()
    print('licD is %s' % licD['id'])

    id_box = libnacl.public.Box(libnacl.encode.hex_decode(id_priv_key), libnacl.encode.hex_decode(pk))
    ids = id_box.decrypt(base64.urlsafe_b64decode(key))
    print('ids is %s' % ids) 

    if ids.decode() == licD['id']:
        print( "SN:%s Licensed to: %s issued: %s expires: %s\n" \
            % (licD['SN'], licD['OWNER'], issueDate, expiresDate))
        return True
    else:
        "*** NOT ACTIVATED : *** Invalid license SN:%s issued to:\n%s\n" \
        % (licD['SN'], licD['OWNER'])
        return False
 

def main():
    args = get_arguments()

    license_client = get_license_file(args)
	
    licD = parse_lic_file(license_client)

    result = verify_lic(licD)
    
    if result is True:
        data = {'status': 'OK', 'filename':license_client['filename']}
    else:
        data = {'status': 'FAIL', 'filename':license_client['filename']}
    
    format_data = parse.urlencode(data).encode('utf-8')

    req = request.Request('http://127.0.0.1:9000/license/status/', format_data)

    resp = request.urlopen(req)

    return 0 


if __name__=="__main__":
    sys.exit(main())
