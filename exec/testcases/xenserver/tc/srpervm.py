# XenRT: Test harness for Xen and the XenServer product family
#
# Test cases for issues with lots of SRs.
#
# Copyright (c) 2012 Citrix Systems, Inc. All use and distribution of this
# copyrighted material is governed by and subject to terms and
# conditions as licensed by Citrix Systems, Inc. All other rights reserved.

import xenrt

class SetupSRs(xenrt.TestCase):
    def run(self, arglist=[]):
        args = self.parseArgsKeyValue(arglist)

        linuxLunCount = int(args.get("linuxluns", "10"))
        windowsLunCount = int(args.get("windowsluns", "10"))

        windowsFilerName = args.get("windowsfiler", None)
        linuxFilerName = args.get("linuxfiler", None)

        linuxFiler = xenrt.StorageArrayFactory().getStorageArray(xenrt.StorageArrayVendor.NetApp, xenrt.StorageArrayType.iSCSI, specify=linuxFilerName)
        windowsFiler = xenrt.StorageArrayFactory().getStorageArray(xenrt.StorageArrayVendor.NetApp, xenrt.StorageArrayType.iSCSI, specify=windowsFilerName)


        pool = self.getDefaultHost().getPool()
        [x.enableMultipathing() for x in pool.getHosts()]
        initiators = dict((x.getName(), {'iqn': x.getIQN()}) for x in pool.getHosts())

        linuxFiler.provisionLuns(linuxLunCount, 10, initiators)
        windowsFiler.provisionLuns(windowsLunCount, 30, initiators)

        i = 0
        for lun in linuxFiler.getLuns():
            sr = xenrt.lib.xenserver.ISCSIStorageRepository(pool.master, "LinuxSR_%d" % i)
            sr.create(lun.getISCSILunObj(), noiqnset=True, subtype="lvm")
            i+=1
        i = 0
        for lun in windowsFiler.getLuns():
            sr = xenrt.lib.xenserver.ISCSIStorageRepository(pool.master, "WindowsSR_%d" % i)
            sr.create(lun.getISCSILunObj(), noiqnset=True, subtype="lvm")
            i+=1

class CopyVMs(xenrt.TestCase):
    def run(self, arglist=[]):
       
        wingold = self.getGuest("wingold")
        wingold.setState("DOWN")
        lingold = self.getGuest("lingold")
        lingold.setState("DOWN")
        host = self.getDefaultHost()

        i = 0
        while True:
            srs = host.minimalList("sr-list", args="name-label=\"LinuxSR_%d\"" % i)
            if not srs:
                break
            sr = srs[0]

            g = lingold.copyVM(name="linclone-%d" % i, sruuid=sr)
            xenrt.GEC().registry.guestPut("linclone-%d" % i, g)
            g.start(specifyOn=False)
            i += 1
        
        i = 0
        while True:
            srs = host.minimalList("sr-list", args="name-label=\"WindowsSR_%d\"" % i)
            if not srs:
                break
            sr = srs[0]

            g = wingold.copyVM(name="winclone-%d" % i, sruuid=sr)
            g.start(specifyOn=False)
            xenrt.GEC().registry.guestPut("winclone-%d" % i, g)
            i += 1

        self.pause("Environment set up")
