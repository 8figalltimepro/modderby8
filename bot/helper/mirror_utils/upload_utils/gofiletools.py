import os
import mimetypes
import requests
from requests_toolbelt import MultipartEncoder
from requests_toolbelt.multipart.encoder import MultipartEncoderMonitor
from bot import GOFILE, GOFILEBASEFOLDER, GOFILETOKEN, LOGGER, DOWNLOAD_DIR, SERVERNUMBER
from logging import getLogger, WARNING
from time import time, sleep
from threading import RLock
from bot.helper.ext_utils.bot_utils import get_readable_file_size
from bot.helper.ext_utils.fs_utils import get_path_size

LOGGER = getLogger(__name__)
getLogger("MultiPartEncoder").setLevel(WARNING)
servernumber = SERVERNUMBER

token = GOFILETOKEN

class GoFileUploader:
    def __init__(self, name=None, listener=None, createdfolderid=None):
        self.__listener = listener
        self.uploaded_bytes = 0
        self.__start_time = time()
        self.__is_cancelled = False
        self.createdfolderid = createdfolderid
        self.name = name
        self.__foldercount = 0
        self.__filecount = 0
        self.__mimetype = 'Folder'
        self.__onlyfile = False
        self.folderpathd = []
        self.__resource_lock = RLock()

    def callback(self, monitor, chunk=(1024 * 1024 * 30), bytesread=0, bytestemp=0):
        bytesread += monitor.bytes_read
        bytestemp += monitor.bytes_read
        if bytestemp > chunk:
            self.uploaded_bytes = bytesread
            bytestemp = 0
        return

    def uploadThis(self):
        path = f"{DOWNLOAD_DIR}{self.__listener.uid}"
        size = get_readable_file_size(get_path_size(path))
        if os.path.isfile(path + r'/{}'.format(self.name)):
            self.gofileupload_(filepath=(path + r'/{}'.format(self.name)), parentfolderid=self.createdfolderid)
        else:    
            self.uploadNow(path + r'/{}'.format(self.name), self.createdfolderid)
        self.folderpathd = []
        if self.__listener.isdrive == False:
            if self.__onlyfile:
                self.__listener.onUploadComplete(None, size, self.__filecount, self.__foldercount, self.__mimetype, self.name)
            else:
                self.__listener.onUploadComplete(None, size, self.__filecount, self.__foldercount, "Folder", self.name)
        return

    def uploadNow(self, path, createdfolderid):  
        files = os.listdir(path)
        self.folderpathd.append(createdfolderid)
        for f in files:
            if os.path.isfile(path + r'/{}'.format(f)):
                self.gofileupload_(filepath=(path + r'/{}'.format(f)), parentfolderid=self.folderpathd[-1])
            elif os.path.isdir(path + r'/{}'.format(f)):
                subfolder = self.gofoldercreate_(foldername=f, parentfolderid=self.folderpathd[-1])
                y = subfolder['id']
                self.uploadNow(path + r'/{}'.format(f), y)
        del self.folderpathd[-1]
        return

    def gofileupload_(self, filepath, parentfolderid):
        self.__filecount += 1
        filename = os.path.basename(filepath)
        mimetype = mimetypes.guess_type(filename)
        self.__mimetype = mimetype
        m = MultipartEncoder(
            fields={'file': (filename, open(filepath, 'rb'), mimetype), 'token': token, 'folderId': parentfolderid})
        monitor = MultipartEncoderMonitor(m, self.callback)
        headers = {'Content-Type': monitor.content_type}
        requests.post(f'https://store{servernumber}.gofile.io/uploadFile', data=monitor,
                      headers=headers)
        return 

    def gofoldercreate_(self, foldername, parentfolderid):
        self.__onlyfile = True
        self.__foldercount += 1
        m = {'folderName': foldername, 'token': token, 'parentFolderId': parentfolderid}
        x = requests.put('https://api.gofile.io/createFolder', data=m).json()['data']
        LOGGER.info(f'Created Folder {foldername}')
        return x

    @property
    def speed(self):
        with self.__resource_lock:
            try:
                return self.uploaded_bytes / (time() - self.__start_time)
            except ZeroDivisionError:
                return 0

    def cancel_download(self):
        self.__is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self.name} and deleting the folder")
        d = {'token': token,'contentsId': self.createdfolderid}
        requests.delete('https://api.gofile.io/deleteContent', data=d)
        self.__listener.onUploadError('your upload has been stopped!')
