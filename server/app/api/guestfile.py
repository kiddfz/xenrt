#!/usr/bin/python

from app.api import XenRTAPIPage
from server import PageFactory
import config

import time,string,os,re,traceback

class XenRTGuestFile(XenRTAPIPage):
    def render(self):

        guest_ip = self.request.client_addr
        guest_fname = self.request.matchdict['filename']
        deadline = time.time() + 60

        # Form a path to find the guest file
        fname = "/local/scratch/guestfiles/%s/%s" % (guest_ip, guest_fname)

        while True:
            if os.path.exists(fname):
		        break
            if time.time() > deadline:
                return "Timed out waiting for guest preseed file"
            time.sleep(1)

        try:
            with open(fname) as f:
                data = f.read()
            with open("%s.stamp" % fname, "w") as f:
                f.write("access")
            return data
        except Exception, e:
            traceback.print_exc()
            return "ERROR Exception occurred, see error_log for details"

PageFactory(XenRTGuestFile, "guestfile", "/guestfile/{filename}")
