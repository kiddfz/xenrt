#
# XenRT: Test harness for Xen and the XenServer product family
#
# Testcases for workspace pod features
#
# Copyright (c) 2008 Citrix Systems, Inc. All use and distribution of this
# copyrighted material is governed by and subject to terms and conditions 
# as licensed by Citrix Systems, Inc. All other rights reserved.
#

import string, time, re, os.path, json, random, xml.dom.minidom
import sys, traceback
import xenrt
from xenrt.lazylog import *
import testcases.benchmarks.workloads

class TCStoragePCIPassthrough(xenrt.TestCase):
    def prepare(self, arglist):
        args = self.parseArgsKeyValue(arglist)
        self.host = self.getDefaultHost()
        gname = args.get("guest")
        if gname:
            self.guest = self.getGuest(gname)
        else:
            self.guest = self.host.guests.values()[0]

        self.duration = int(args.get("duration", 0)) * 60

        multipathing = None

        if "multipathing" in args:
            # Set up multipathing for SAS
            self.guest.setState("UP")
            self.guest.xmlrpcExec("Install-WindowsFeature -Name Multipath-IO", powershell=True)
            self.guest.reboot()
            self.guest.xmlrpcExec("Enable-MSDSMAutomaticClaim -BusType SAS", powershell=True)
        
        # Shutdown the guest and pass through the device
        self.guest.setState("DOWN")

        pcipattern = args.get("pci", "LSI")
        pci = self.host.execdom0("lspci | grep '%s'" % pcipattern).splitlines()[0].split()[0]
        self.guest.paramSet("other-config:pci", "0/0000:%s" % pci)

        # Dodgy hack for option ROMs that require "Press Any Key to continue". This will hopefully be addressed before release!
        if xenrt.TEC().lookup("WORKAROUND_CA172261", False, boolean=True):
            self.guest.special['sendbioskey'] = True
        self.guest.start()

        # Find a LUN to use
        mylun = [self.host.lookup(["FC", x]) for x in self.host.lookup("FC").keys() if not self.host.lookup(["FC", x, "SHARED"], True, boolean=True)][0]
       
        # Get the windows disk ID based on the LUN ID. This isn't foolproof if there are 2 targets, so may need improving in future.
        disks = json.loads(self.guest.xmlrpcExec(
            "Get-WmiObject -Class win32_diskdrive | Where {$_.SCSILogicalUnit -eq %d} | Select Name | ConvertTo-Json -Compress" % int(mylun['LUNID']),
            powershell=True,
            returndata=True).strip().splitlines()[-1])

        mydisk = [re.search("PHYSICALDRIVE(\d+)", x['Name']).group(1) for x in disks if not x['Name'].endswith("PHYSICALDRIVE0")][0]

        if mylun.get('MPCLAIM'):
            # Find out which MPIO disk we need to work on
            mpiodisk = [re.search("^MPIO Disk(\d+)", x).group(1) for x in self.guest.xmlrpcExec("mpclaim -s -d", returndata=True).splitlines() if " Disk %s " % mydisk in x][0]
            
            # Get all of the available paths
            valid = False
            paths = []
            for x in self.guest.xmlrpcExec("mpclaim -s -d 0", returndata=True).splitlines():
                if valid:
                    m = re.match("^\s+(\d+)", x)
                    if m:
                        paths.append(m.group(1))
                if "-----------------------" in x:
                    valid = True

            # Build up the mpclaim command by replacing regular expressions with concrete paths.
            cmd = mylun['MPCLAIM']
            subs = re.findall("\{PATH:.+?\}", cmd)
            for s in subs:
                regex = re.match("\{PATH:(.*)\}", s).group(1)
                for p in paths:
                    if re.match("^%s$" % regex, p):
                        cmd = cmd.replace(s, p)
                        break

            self.guest.xmlrpcExec("mpclaim -l -d %s %s" % (mpiodisk, cmd))
        
        # Clean, initialise and format the disk
        self.guest.xmlrpcDiskpartCommand("rescan")
        self.guest.xmlrpcDiskpartCommand("select disk %s\nclean" % mydisk)
        self.guest.xmlrpcDiskpartCommand("rescan")
        self.guest.xmlrpcInitializeDisk(mydisk)
        self.guest.xmlrpcFormat("e", quick=True)

        # Install FIO
        self.fio = testcases.benchmarks.workloads.FIOWindows(self.guest, drive="e")
        self.fio.install()

    def run(self, arglist):
        deadline = xenrt.timenow() + self.duration
        while True:
            self.fio.runCheck()
            if xenrt.timenow() > deadline:
                break

