# XenRT: Test harness for Xen and the XenServer product family
#
# Test cases for issues with lots of SRs.
#
# Copyright (c) 2012 Citrix Systems, Inc. All use and distribution of this
# copyrighted material is governed by and subject to terms and
# conditions as licensed by Citrix Systems, Inc. All other rights reserved.

import xenrt
import testcases.benchmarks.workloads

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

class TCMonitorLowMem(xenrt.TestCase):

    def startWindowsWorkload(self, guest):
        workload = testcases.benchmarks.workloads.FIOWindows(guest)
        workload.start()
    
    def startLinuxWorkload(self, guest):
        workload = testcases.benchmarks.workloads.FIOLinux(guest)
        workload.start()

    def prepare(self, arglist=[]):
        winguests = []
        linguests = []
        i = 0
        while True:
            g = self.getGuest("winclone-%d" % i)
            if not g:
                break
            winguests.append(g)
            i+=1
        i = 0
        while True:
            g = self.getGuest("linclone-%d" % i)
            if not g:
                break
            linguests.append(g)
            i+=1

        pWindows = map(lambda x: xenrt.PTask(self.startWindowsWorkload, winguests)
        pLinux = map(lambda x: xenrt.PTask(self.startLinuxWorkload, linguests)
        xenrt.pfarm(pWindows)
        xenrt.pfarm(pLinux)

    def run(self, arglist=[]):
        args = self.parseArgsKeyValue(arglist)

        minutes = int(args.get("minutes", "10"))

        pool = self.getDefaultHost().getPool()
        for i in xrange(minutes):
            for h in pool.getHosts():
                lowmem = h.execdom0("echo 3 > /proc/sys/vm/drop_caches && grep LowFree /proc/meminfo | cut -d ':' -f 2").strip()
                xenrt.TEC().logverbose("Low Memory on %s: %s" % (h.getName(), lowmem))
            xenrt.sleep(60)
