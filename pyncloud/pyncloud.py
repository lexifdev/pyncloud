import mimetypes
import os
import re
import shutil
from datetime import datetime
import rsa
import requests


def _naver_style_join(l):
    return ''.join([chr(len(s)) + s for s in l])


def _encrypt(key_str, uid, upw):
    session_key, key_name, e_str, n_str = key_str.split(',')
    e, n = int(e_str, 16), int(n_str, 16)

    message = _naver_style_join([session_key, uid, upw])

    pubkey = rsa.PublicKey(e, n)
    encrypted = rsa.encrypt(message, pubkey)

    return key_name, encrypted.encode('hex')


def get_ndrive(nid, npw):
    key_str = requests.get('http://static.nid.naver.com/enclogin/keys.nhn').content

    encnm, encpw = _encrypt(key_str, nid, npw)

    session = requests.Session()
    response = session.post('https://nid.naver.com/nidlogin.login', data={
        'url': 'www.naver.com',
        'svctype': '0',
        'smart_level': '1',
        'enc_url': 'http0X0.0000000000001P-10220.0000000.000000www.naver.com',
        'enctp': '1',
        'encnm': encnm,
        'encpw': encpw,
    })

    finalize_url = re.search(r'location\.replace\("([^"]+)"\)', response.content).group(1)
    session.get(finalize_url)

    return Ndrive(nid, session)


class NdriveError(Exception):
    class Codes(object):
        NotExistPath = 11

    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return 'NdriveError code="%s" message="%s"' % (self.code, self.message)


class Ndrive(object):
    class Types(object):
        DIR = 1
        FILE = 2
        BOTH = 3

    class TypeNames(object):
        DIR = 'collection'
        FILE = 'property'

    def __init__(self, user_id, session):
        self._userid = user_id
        self._useridx = None
        self._s = session

    @staticmethod
    def _check_error(data):
        if data['resultcode'] != 0:
            raise NdriveError(data['resultcode'], data['message'])

    def check_status(self):
        resp = self._s.get('http://ndrive2.naver.com/GetRegisterUserInfo.ndrive', params={
            'userid': self._userid,
            'svctype': 'Android NDrive App ver',
            'auto': 0
        })
        data = resp.json()
        self._check_error(data)

        self._useridx = data['resultvalue']['useridx']

        return data['resultvalue']

    def _list(self, target_path, kind):
        if not self._useridx:
            self.check_status()

        resp = self._s.post('http://ndrive2.naver.com/GetList.ndrive', data={
            'orgresource': target_path,
            'type': kind,
            'dept': 0,
            'sort': 'name',
            'order': 'asc',
            'startnum': 0,
            'pagingrow': 1000,
            'dummy': 56184,
            'userid': self._userid,
            'useridx': self._useridx,
        })
        data = resp.json()
        self._check_error(data)

        if not data['resultvalue']:
            return []

        return [(x['href'], x) for x in data['resultvalue']]

    def list_dirs(self, target_path):
        return self._list(target_path, self.Types.DIR)

    def list_files(self, target_path):
        return self._list(target_path, self.Types.FILE)

    def make_dir(self, target_path):
        if not self._useridx:
            self.check_status()

        resp = self._s.post('http://ndrive2.naver.com/MakeDirectory.ndrive', data={
            'dstresource': target_path,
            'userid': self._userid,
            'useridx': self._useridx,
            'dummy': 40841,
        })
        data = resp.json()
        self._check_error(data)

        return True

    def get_disk_space(self):
        if not self._useridx:
            self.check_status()

        resp = self._s.post('http://ndrive2.naver.com/GetDiskSpace.ndrive', data={
            'userid': self._userid,
            'useridx': self._useridx,
        })
        data = resp.json()
        self._check_error(data)

        return data['resultvalue']['unusedspace']

    def check_upload(self, target_path, fp, overwrite=True):
        if not self._useridx:
            self.check_status()

        file_stat = os.fstat(fp.fileno())

        resp = self._s.post('http://ndrive2.naver.com/CheckUpload.ndrive', data={
            'userid': self._userid,
            'useridx': self._useridx,
            'overwrite':  'T' if overwrite else 'F',
            'uploadsize': file_stat.st_size,
            'getlastmodified': datetime.datetime.fromtimestamp(file_stat.st_mtime),
            'dstresource': target_path,
        })
        data = resp.json()
        self._check_error(data)

        return True

    def get_fileinfo(self, target_path):
        if not self._useridx:
            self.check_status()

        resp = self._s.post('http://ndrive2.naver.com/GetProperty.ndrive', data={
            'orgresource': target_path,
            'userid': self._userid,
            'useridx': self._useridx,
            'dummy': 56184,
        })
        data = resp.json()
        self._check_error(data)

        return data['resultvalue']

    def exists(self, target_path):
        try:
            self.get_fileinfo(target_path)
            return True
        except NdriveError as e:
            if e.code != NdriveError.Codes.NotExistPath:
                raise e
            return False

    def upload(self, target_path, fp, overwrite=True):
        if not self._useridx:
            self.check_status()

        # self.get_disk_space()
        # self.check_upload(target_path, fp, overwrite)

        file_stat = os.fstat(fp.fileno())
        mime = mimetypes.guess_type(target_path)[0]

        resp = self._s.put('http://ndrive2.naver.com' + target_path, data=fp, headers={
            'userid': self._userid,
            'useridx': self._useridx,
            'MODIFYDATE': datetime.fromtimestamp(file_stat.st_mtime),
            'Content-Type': mime or 'application/octet-binary',
            'charset': 'UTF-8',
            'Origin': 'http://ndrive2.naver.com',
            'OVERWRITE': 'T' if overwrite else 'F',
            'X-Requested-With': 'XMLHttpRequest',
            'NDriveSvcType': 'NHN/DRAGDROP Ver',
        })

        data = resp.json()
        self._check_error(data)

        return True

    def download(self, remote_path, local_path):
        if not self._useridx:
            self.check_status()

        resp = self._s.get('http://ndrive2.naver.com' + remote_path, params={
            'attachment': 2,
            'userid': self._userid,
            'useridx': self._useridx,
            'NDriveSvcType': 'NHN/ND-WEB Ver',
        }, stream=True)

        dirname = os.path.dirname(local_path)
        if not os.path.isdir(dirname) or not os.path.exists(dirname):
            os.makedirs(dirname)

        resp.raw.decode_content = True
        shutil.copyfileobj(resp.raw, open(local_path, 'wb+'))

    def move(self, from_path, to_path):
        if not self._useridx:
            self.check_status()

        resp = self._s.post('http://ndrive2.naver.com/DoMove.ndrive', data={
            'userid': self._userid,
            'useridx': self._useridx,
            'orgresource': from_path,
            'dstresource': to_path,
            'overwrite': 'T',
            'bShareFireCopy': 'false',
            'dummy': 56147,
        })

        data = resp.json()
        self._check_error(data)

        return True
