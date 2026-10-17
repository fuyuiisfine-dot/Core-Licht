import json
import struct
import unittest
from tools.repack_lan_apk import decode_blob


class ApkContainerTests(unittest.TestCase):
    def test_binary_url_container_preserves_header_and_unicode_payload(self):
        header=b'\x07LXT_SHA\x13UrlList_Android.txt'
        payload=json.dumps({'name':'區網','baseUrl':'http://192.168.0.124:18080/'}).encode()
        preserved,config=decode_blob(header+struct.pack('<I',len(payload))+payload)
        self.assertEqual(preserved,header)
        self.assertEqual(config['name'],'區網')

    def test_rejects_wrong_asset_and_truncated_payload(self):
        with self.assertRaises(ValueError):decode_blob(b'\x07WRONG__\x13UrlList_Android.txt'+struct.pack('<I',2)+b'{}')
        with self.assertRaises(ValueError):decode_blob(b'\x07LXT_SHA\x13UrlList_Android.txt'+struct.pack('<I',8)+b'{}')


if __name__=='__main__':unittest.main()
