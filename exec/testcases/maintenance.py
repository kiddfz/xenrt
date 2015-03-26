#
# XenRT: Test harness for Xen and the XenServer product family
#
# Harness and infrastructure maintenance testcases
#
# Copyright (c) Citrix Systems, Inc. All use and distribution of this
# copyrighted material is governed by and subject to terms and
# conditions as licensed by Citrix Systems, Inc. All other rights reserved.
#

import sys, re, string, os.path, urllib, traceback, time, shutil, stat, os
import xenrt
from xenrt.lazylog import step, comment, log, warning

class TCSiteStatus(xenrt.TestCase):
    """Record items of XenRT site status in result fields."""
    
    def run(self, arglist=[]):

        for var in ["XENRT_VERSION"]:
            value = xenrt.TEC().lookup(var, None)
            if value:
                self.tec.appresult("%s=%s" % (var, value))

class TCSyncRPMs(xenrt.TestCase):
    """Synchronise local RPM/deb repositories with the central repository"""

    def doRepo(self, distro, arch):
        nfspaths = xenrt.TEC().lookup(["RPM_SOURCE", distro, arch, "NFS"],
                                      None)
        if not nfspaths:
            raise xenrt.XRTError("No NFS path configured for %s %s" %
                                 (distro, arch))
        masterpaths = xenrt.TEC().lookup(\
            ["MASTER_RPM_PATHS", distro, arch, "PATH"], None)
        if not masterpaths:
            raise xenrt.XRTError("No master path configured for %s %s" %
                                 (distro, arch))
        nfspathlist = nfspaths.split()
        masterpathlist = masterpaths.split()
        if len(nfspathlist) != len(masterpathlist):
            raise xenrt.XRTError("Length of master path list and NFS path "
                                 "list differ for %s %s" % (distro, arch),
                                 "NFS=%s; PATH=%s" % (nfspaths, masterpaths))

        for i in range(len(nfspathlist)):
            masterpath = masterpathlist[i]
            nfspath = nfspathlist[i]
            
            # Create a mountpoint for the NFS repo and mount it
            # Note that a new distro will not yet have a directory on the file
            # server for the distro so the mount point will not exist. In this
            # case try mounting further up the path and create the directory
            # heirarchy as necessary.
            mount = None
            try:
                mount = xenrt.MountNFS(nfspath, retry=False)
            except xenrt.XRTException, e:
                if e.data and ("No such file or directory" in e.data or
                               "Permission denied" in e.data or
                               "access denied" in e.data):
                    # Try to create the path by mounting parent directories
                    pathdirs = nfspath.split(":")[1].split("/")
                    server = nfspath.split(":")[0]
                    done = False
                    for i in range(len(pathdirs) - 1, 0, -1):
                        try:
                            nfspathx = "%s:%s" % (server,
                                                  string.join(pathdirs[0:i],
                                                              "/"))
                            makepath = string.join(pathdirs[i:], "/")
                            xenrt.TEC().logverbose("Trying to create %s in %s"
                                                   % (makepath, nfspathx))
                            mountx = xenrt.MountNFS(nfspathx, retry=False)
                            try:
                                mountpointx = mountx.getMount()
                                try:
                                    os.makedirs("%s/%s" %
                                                (mountpointx, makepath))
                                    done = True
                                except Exception, e:
                                    raise xenrt.XRTError(\
                                        "Unable to create directory %s in %s" %
                                        (makepath, nfspathx))
                            finally:
                                mountx.unmount()
                        except xenrt.XRTException, e:
                            if e.data and \
                                   ("No such file or directory" in e.data or
                                    "Permission denied" in e.data or
                                    "access denied" in e.data):
                                # Try a level further up the path
                                pass
                            else:
                                raise e
                        if done:
                            break
                    if not done:
                        raise xenrt.XRTError(\
                            "Unable to create new export path")
                    mount = xenrt.MountNFS(nfspath, retry=False)
            try:
                mountpoint = mount.getMount()
            
                # Perform the rsync
                rsynccmd = self.rsynccmdstem + masterpath + "/ " + \
                           mountpoint + "/"
                xenrt.TEC().logverbose(rsynccmd)
                xenrt.command(rsynccmd, timeout=36000)
            finally:
                try:
                    if mount:
                        mount.unmount()
                except:
                    pass

    def run(self, arglist=[]):

        # If we do not manage the repos (e.g. if we share a NFS server
        # with another site which performs the management) then
        # skip
        if xenrt.TEC().lookup("MASTER_RPM_UNMANAGED", False, boolean=True):
            self.tec.skip("This site does not manage RPM repos")
            return

        # Form the stem of the rsync command
        syncuser = xenrt.TEC().lookup("MASTER_RPM_SYNC_USER", None)
        synchost = xenrt.TEC().lookup("MASTER_RPM_SYNC_HOST", None)
        syncrsh = xenrt.TEC().lookup("MASTER_RPM_SYNC_RSH", None)
        syncoptions = xenrt.TEC().lookup("RSYNC_OPTIONS", None)
        if not synchost:
            raise xenrt.XRTError("No MASTER_RPM_SYNC_HOST configured")
        self.rsynccmdstem = "rsync -avxl"
        if syncoptions:
            self.rsynccmdstem = self.rsynccmdstem + " %s" % syncoptions
        if syncrsh:
            # If we reference the SSH_PRIVATE_KEY_FILE then make a copy
            # of this with suitable permissions for ssh use
            sshkeyfile = xenrt.TEC().lookup("SSH_PRIVATE_KEY_FILE", None)
            if sshkeyfile and sshkeyfile in syncrsh:
                xenrt.TEC().logverbose("Making chmod 600 version of SSH key")
                sshkeyfile600 = xenrt.TEC().tempFile()
                shutil.copy(sshkeyfile, sshkeyfile600)
                shutil.copy("%s.pub" % (sshkeyfile),
                            "%s.pub" % (sshkeyfile600))
                os.chmod(sshkeyfile600, stat.S_IRWXU)
                os.chmod("%s.pub" % (sshkeyfile600), stat.S_IRWXU)
                syncrsh = syncrsh.replace(sshkeyfile, sshkeyfile600)
            self.rsynccmdstem = self.rsynccmdstem + " -e '%s'" % (syncrsh)
        if syncuser:
            self.rsynccmdstem = self.rsynccmdstem + " %s@%s:" % (syncuser,
                                                                 synchost)
        else:
            self.rsynccmdstem = self.rsynccmdstem + " %s:" % (synchost)


        # We'll only update things we have configured
        distros = xenrt.TEC().lookup("RPM_SOURCE", {})
        for distro in distros.keys():
            arches = xenrt.TEC().lookup(["RPM_SOURCE", distro], {})
            for arch in arches.keys():
                self.runSubcase("doRepo", (distro, arch), distro, arch)
                if xenrt.GEC().abort:
                    raise xenrt.XRTError("Aborting on command")

class _TCSyncDir(xenrt.TestCase):
    """Synchronise local ISO exports with the central repository"""

    LOCAL_NFS_PATH = None
    UNMANAGED_FLAG = None
    SYNC_USER = None
    SYNC_HOST = None
    SYNC_RSH = None
    MASTER_DIR = None

    def run(self, arglist=[]):

        # If we do not have a ISO export then skip
        if not xenrt.TEC().lookup(self.LOCAL_NFS_PATH, None):
            self.tec.skip("This site does not have a %s" %
                          (self.LOCAL_NFS_PATH))
            return

        # If we do not manage the export (e.g. if we share a NFS server
        # with another site which performs the management) then
        # skip
        if xenrt.TEC().lookup(self.UNMANAGED_FLAG,
                              False,
                              boolean=True):
            self.tec.skip("This site does not manage the ISO export")
            return

        # Form the stem of the rsync command
        syncuser = xenrt.TEC().lookup(self.SYNC_USER, None)
        synchost = xenrt.TEC().lookup(self.SYNC_HOST, None)
        syncrsh = xenrt.TEC().lookup(self.SYNC_RSH, None)
        syncoptions = xenrt.TEC().lookup("RSYNC_OPTIONS", None)
        if not synchost:
            raise xenrt.XRTError("No %s configured" % (self.SYNC_HOST))
        self.rsynccmdstem = "rsync -avxl"
        if syncoptions:
            self.rsynccmdstem = self.rsynccmdstem + " %s" % syncoptions
        if syncrsh:
            # If we reference the SSH_PRIVATE_KEY_FILE then make a copy
            # of this with suitable permissions for ssh use
            sshkeyfile = xenrt.TEC().lookup("SSH_PRIVATE_KEY_FILE", None)
            if sshkeyfile and sshkeyfile in syncrsh:
                xenrt.TEC().logverbose("Making chmod 600 version of SSH key")
                sshkeyfile600 = xenrt.TEC().tempFile()
                shutil.copy(sshkeyfile, sshkeyfile600)
                shutil.copy("%s.pub" % (sshkeyfile),
                            "%s.pub" % (sshkeyfile600))
                os.chmod(sshkeyfile600, stat.S_IRWXU)
                os.chmod("%s.pub" % (sshkeyfile600), stat.S_IRWXU)
                syncrsh = syncrsh.replace(sshkeyfile, sshkeyfile600)
            self.rsynccmdstem = self.rsynccmdstem + " -e '%s'" % (syncrsh)
        if syncuser:
            self.rsynccmdstem = self.rsynccmdstem + " %s@%s:" % (syncuser,
                                                                 synchost)
        else:
            self.rsynccmdstem = self.rsynccmdstem + " %s:" % (synchost)

        nfspath = xenrt.TEC().lookup(self.LOCAL_NFS_PATH)
        masterpath = xenrt.TEC().lookup(self.MASTER_DIR, None)
        if not masterpath:
            raise xenrt.XRTError("No master path configured")
            
        # Create a mountpoint for ISOs
        if nfspath.startswith("%s:" %
                              (xenrt.TEC().lookup("XENRT_SERVER_ADDRESS"))):
            # It's a local controller export, shortcut by not mounting and
            # copying directly in.
            mount = None
            mountpoint = nfspath.split(":")[1]
        else:
            mount = xenrt.MountNFS(nfspath, retry=False)
            mountpoint = mount.getMount()
        try:
            # Perform the rsync
            rsynccmd = self.rsynccmdstem + masterpath + "/ " + \
                       mountpoint + "/"
            xenrt.TEC().logverbose(rsynccmd)
            xenrt.command(rsynccmd, timeout=360000)
        finally:
            try:
                if mount:
                    mount.unmount()
            except:
                pass

class TCSyncLinuxISOs(_TCSyncDir):
    """Synchronise local Linux ISO exports with the central repository"""

    # Names of the site variables for this export
    LOCAL_NFS_PATH = "EXPORT_ISO_NFS_STATIC"
    UNMANAGED_FLAG = "MASTER_LINUX_ISOS_UNMANAGED"
    SYNC_USER = "MASTER_LINUX_ISOS_SYNC_USER"
    SYNC_HOST = "MASTER_LINUX_ISOS_SYNC_HOST"
    SYNC_RSH = "MASTER_LINUX_ISOS_SYNC_RSH"
    MASTER_DIR = "MASTER_LINUX_ISOS_DIR"

class TCSyncWindowsISOs(_TCSyncDir):
    """Synchronise local Windows ISO exports with the central repository"""

    # Names of the site variables for this export
    LOCAL_NFS_PATH = "EXPORT_ISO_NFS"
    UNMANAGED_FLAG = "MASTER_WINDOWS_ISOS_UNMANAGED"
    SYNC_USER = "MASTER_WINDOWS_ISOS_SYNC_USER"
    SYNC_HOST = "MASTER_WINDOWS_ISOS_SYNC_HOST"
    SYNC_RSH = "MASTER_WINDOWS_ISOS_SYNC_RSH"
    MASTER_DIR = "MASTER_WINDOWS_ISOS_DIR"

class TCSyncDistFiles(_TCSyncDir): 
    """Synchronise local distfiles with the central repository"""

    # Names of the site variables for this export
    LOCAL_NFS_PATH = "EXPORT_DISTFILES_NFS"
    UNMANAGED_FLAG = "MASTER_DISTFILES_UNMANAGED"
    SYNC_USER = "MASTER_DISTFILES_SYNC_USER"
    SYNC_HOST = "MASTER_DISTFILES_SYNC_HOST"
    SYNC_RSH = "MASTER_DISTFILES_SYNC_RSH"
    MASTER_DIR = "MASTER_DISTFILES_DIR"

class TCPrepareDellUpdate(xenrt.TestCase):
    def run(self, arglist=[]):
        host = self.getDefaultHost()
        host.execdom0("wget -q -O - http://linux.dell.com/repo/hardware/latest/bootstrap.cgi | bash")
        host.execdom0("yum install srvadmin-all -y", timeout=3600)
        host.execdom0("yum install dell_ft_install -y", timeout=3600)
        host.execdom0("yum install $(bootstrap_firmware) -y", timeout=3600)
        host.execdom0("inventory_firmware", timeout=3600)
        host.execdom0("update_firmware", timeout=3600)

class TCPerformDellUpdate(xenrt.TestCase):
    def run(self, arglist=[]):
        host = self.getDefaultHost()
        host.execdom0("update_firmware --yes", timeout=7200)
        host.reboot()


class TCSysInfo(xenrt.TestCase):
    
    def prepare(self, arglist):
        self.host = self.getDefaultHost()
    
    def run(self, arglist=[]):
        cli = self.host.getCLIInstance()
        
        # 1. Memory

        memorystring = cli.execute("host-list params=memory-total")
        matches = re.search("memory-total.*?: (\d*)",memorystring)
        membytes = float(matches.group(1))
        memgigabytes = int(round(membytes/xenrt.GIGA))

        # 2. Disks

        diskinfo = []
        disks = []
        diskstring = self.host.execdom0("ls -l /dev/disk/by-path")
        for line in diskstring.splitlines():
            matches = re.search("(ide|scsi|sas)(.*)->\s\.\./\.\./(.*)", line)
            if matches != None:
                if re.search("part", matches.group(2)) == None:
                    disks.append(matches.group(3))
        for disk in disks:
            fdiskout = self.host.execdom0("fdisk -l /dev/%s" % disk)
            for line in fdiskout.splitlines():
                matches = re.search("Disk /dev/%s: (.*) GB" % disk, line)
                if matches != None:
                    diskinfo.append(int(round(float(matches.group(1)))))

        # 3. CPUs
        xecpustring = cli.execute("host-cpu-info")
        xecpulines = xecpustring.split("\n")
        cpucount = ""
        vendor = ""
        speed = ""
        flags = ""
        modelname = ""
        model = ""
        family = ""
        stepping = ""
        maskable = ""
        features = ""
        for xecpuline in xecpulines:
            matches = re.search("^\s*?cpu_count.*?: (.*)",xecpuline)
            if matches != None:
                cpucount = matches.group(1)
            matches = re.search("vendor\s*?: (.*)",xecpuline)
            if matches != None:
                vendor =  matches.group(1)
            matches = re.search("flags\s*?: (.*)",xecpuline)
            if matches != None:
                flags =  matches.group(1)
            matches = re.search("speed\s*?: (.*)",xecpuline)
            if matches != None:
                speed =  matches.group(1)
            matches = re.search("modelname\s*?: (.*)",xecpuline)
            if matches != None:
                modelname =  matches.group(1)
            matches = re.search("model\s*?: (.*)",xecpuline)
            if matches != None:
                model =  matches.group(1)
            matches = re.search("family\s*?: (.*)",xecpuline)
            if matches != None:
                family =  matches.group(1)
            matches = re.search("stepping\s*?: (.*)",xecpuline)
            if matches != None:
                stepping =  matches.group(1)
            matches = re.search("physical_features\s*?: (.*)",xecpuline)
            if matches != None:
                features =  matches.group(1)
            matches = re.search("maskable\s*?: (.*)",xecpuline)
            if matches != None:
                maskable =  matches.group(1)
        dmicpustring = self.host.execdom0("dmidecode -t 4")
        dmicpulines = dmicpustring.split("\n")

        socketcount = 0
        threadcount = 0
        corecount = 0

        for dmicpuline in dmicpulines:
            matches = re.search("Processor Information",dmicpuline) 
            if matches != None:
                socketcount = socketcount + 1
            matches = re.search("Core Count: (.*)",dmicpuline)
            if matches != None:
                corecount = corecount + int(matches.group(1))
            matches = re.search("Thread Count: (.*)",dmicpuline)
            if matches != None:
                threadcount = threadcount + int(matches.group(1))
        if int(cpucount) != threadcount: 
            xenrt.TEC().warning("CPU count from xe host-cpu-list did not match Thread count from DMI Decode, results cannot be trusted")

        if corecount == 0:
            corecount = int(cpucount) # Assume no hyperthreading if we can't work it out from dmidecode
        # 5. Network cards:

        pcistring = self.host.execdom0("lspci")
        pcilines = pcistring.split("\n")

        ethinfo = []

        for pciline in pcilines:
            matches = re.search("Ethernet", pciline)
            if matches != None:
                matches = re.search("Virtual Function", pciline)
                if matches == None:
                    ethinfo.append(pciline)
       
        # 6. Network interfaces

        nics = self.host.listSecondaryNICs()
        networks = {'NPRI' : 1}
        for nic in nics:
            net = self.host.getNICNetworkName(nic)
            if net != 'none':
                if net not in networks:
                    networks[net] = 0
                networks[net] = networks[net] + 1

            

        xenrt.TEC().appresult("CPU: Socket count: %d" % socketcount)
        xenrt.TEC().appresult("CPU: Core count: %d" % corecount)
        xenrt.TEC().appresult("CPU: Logical CPU count: %s" % cpucount)
        xenrt.TEC().appresult("CPU: Vendor: %s " % vendor)
        xenrt.TEC().appresult("CPU: Speed: %sMHz" % speed)
        xenrt.TEC().appresult("CPU: Model name: %s" % modelname)
        xenrt.TEC().appresult("CPU: Family - %s, Model - %s, Stepping - %s" % (family, model, stepping))
        xenrt.TEC().appresult("CPU: Flags: %s" % flags)
        xenrt.TEC().appresult("CPU: Features: %s" % features)
        xenrt.TEC().appresult("CPU: Features Maskable: %s" % maskable)
        xenrt.TEC().appresult("Memory: %dG" % memgigabytes)
        xenrt.TEC().appresult("Disks: %d" % len(diskinfo))
        resourcestring = "memory=%dG/sockets=%d/cores=%d/cpus=%s/disks=%d" % (memgigabytes, socketcount, corecount, cpucount, len(diskinfo))
        diskcount = 0
        for disk in diskinfo:
            diskcount = diskcount + 1
            xenrt.TEC().appresult("Disk %d: %dG" % (diskcount, disk))
            resourcestring = resourcestring + "/disk%d=%dG" % (diskcount, disk)
        xenrt.TEC().appresult("NICs: %d" % len(ethinfo))
        ethcount = 0
        for eth in ethinfo:
            ethcount = ethcount + 1
            xenrt.TEC().appresult("NIC %d: %s" %(ethcount, eth))

        for network in networks.iterkeys():
            xenrt.TEC().appresult("NICs on %s: %d" % (network, networks[network]))
            resourcestring = resourcestring + "/%s=%d" % (network, networks[network])
        xenrt.TEC().appresult("Resource string: %s" % resourcestring)
        dmistring = self.host.execdom0("dmidecode")
        filename = "%s/dmidecode.log" % (xenrt.TEC().getLogdir())
        f = file(filename, "w")
        f.write(dmistring)
        f.close()
        
        filename = "%s/lspci.log" % (xenrt.TEC().getLogdir())
        f = file(filename, "w")
        f.write(pcistring)
        f.close()

class TCUnsupFlags(xenrt.TestCase):
    ALL_FLAGS = {
# XenServer
"unsup_6.0"     : { "productVersion":"Boston",      "isSetIfPass":False, "version":"/usr/groups/release/XenServer-6.x/XS-6.0.0/RTM-50762" },
"unsup_6.0.2"   : { "productVersion":"Sanibel",     "isSetIfPass":False, "version":"/usr/groups/release/XenServer-6.x/XS-6.0.2/RTM-53456" },
"unsup_6.1"     : { "productVersion":"Tampa",       "isSetIfPass":False, "version":"/usr/groups/release/XenServer-6.x/XS-6.1.0/RTM" },
"unsup_6.2"     : { "productVersion":"Clearwater",  "isSetIfPass":False, "version":"/usr/groups/release/XenServer-6.x/XS-6.2/RTM-70446" },
"unsup_6.5"     : { "productVersion":"Creedence",   "isSetIfPass":False, "version":"/usr/groups/release/XenServer-6.x/XS-6.5/RTM-90233" },
"unsup_7"       : { "productVersion":"Dundee",      "isSetIfPass":False, "version":"/usr/groups/build/trunk/latest" },
# ESXi VMware
"unsup_vmware55"    : { "productType" : "esx",      "productVersion":"5.5.0-update02",      "isSetIfPass": False },
"unsup_vmware51"    : { "productType" : "esx",      "productVersion":"5.1.0",               "isSetIfPass": False },
"unsup_vmware5"     : { "productType" : "esx",      "productVersion":"5.0.0.update01",      "isSetIfPass": False },
# HyperV
"unsup_ws12r2"      : { "productType":"hyperv",     "productVersion":"ws12r2-x64",          "isSetIfPass": False },
"unsup_hvs12r2"     : { "productType":"hyperv",     "productVersion":"hvs12r2-x64",         "isSetIfPass": False },
# KVM
"unsup_rhel63"      : { "productType":"kvm",        "productVersion":"rhel63_x86-64",       "isSetIfPass": False },
"unsup_rhel64"      : { "productType":"kvm",        "productVersion":"rhel64_x86-64",       "isSetIfPass": False },
"unsup_rhel65"      : { "productType":"kvm",        "productVersion":"rhel65_x86-64",       "isSetIfPass": False },
# Native Linux
"unsup_centos6x32"  : { "productType":"nativelinux", "productVersion":"centos6_x86-32",     "isSetIfPass": False },
"unsup_centos6"     : { "productType":"nativelinux", "productVersion":"centos6_x86-64",     "isSetIfPass": False },
"unsup_centos7"     : { "productType":"nativelinux", "productVersion":"centos7_x86-64",     "isSetIfPass": False },
"unsup_debian7x32"  : { "productType":"nativelinux", "productVersion":"debian70_x86-32",    "isSetIfPass": False },
"unsup_debian7"     : { "productType":"nativelinux", "productVersion":"debian70_x86-64",    "isSetIfPass": False },
"unsup_oel6x32"     : { "productType":"nativelinux", "productVersion":"oel6_x86-32",        "isSetIfPass": False },
"unsup_oel6"        : { "productType":"nativelinux", "productVersion":"oel6_x86-64",        "isSetIfPass": False },
"unsup_oel7"        : { "productType":"nativelinux", "productVersion":"oel7_x86-64",        "isSetIfPass": False },
"unsup_rhel6x32"    : { "productType":"nativelinux", "productVersion":"rhel6_x86-32",       "isSetIfPass": False },
"unsup_rhel6"       : { "productType":"nativelinux", "productVersion":"rhel6_x86-64",       "isSetIfPass": False },
"unsup_rhel7"       : { "productType":"nativelinux", "productVersion":"rhel7_x86-64",       "isSetIfPass": False }
    }

    def createTempSeq(self, productType=None, productVersion=None, version=None, **kargs):
        seq = "tempSeq.seq"
        seqContent  = """<xenrt><prepare><host id="0" """
        seqContent += 'productType="%s" ' % productType if productType else ""
        seqContent += 'productVersion="%s" '% productVersion if productVersion else ""
        seqContent += 'version="%s" ' % version if version else ""
        seqContent += """/></prepare></xenrt>"""
        seqFile ="%s/seqs/tempSeq.seq" % xenrt.TEC().lookup("XENRT_BASE", "/usr/share/xenrt")
        with open("%s/seqs/%s" % (xenrt.TEC().lookup("XENRT_BASE"), seq), 'w') as seqFile:
            seqFile.write(seqContent)
        log("Temp Seq file content : %s" % seqContent)
        return seq

    def doSequence(self, seqFileName):
        seqFile = xenrt.findSeqFile(seqFileName)
        seq = xenrt.TestSequence(seqFile)
        seq.doPreprepare()
        seq.doPrepare()

    def isPropAlreadySet(self, flag):
        return flag in xenrt.util.command('xenrt machine %s | grep -e "^PROPS"' % (self.machineName))

    def prepare(self, arglist):
        self.machineName = xenrt.PhysicalHost(xenrt.TEC().lookup("RESOURCE_HOST_0")).name
        self.flags = {}
        self.updateMachine = False

        args = self.parseArgsKeyValue(arglist)
        if "FLAGSTOCHECK" in args:
            [ self.flags.update({ flag:self.ALL_FLAGS[flag] }) for flag in args["FLAGSTOCHECK"].split(",") if flag in self.ALL_FLAGS]
        elif "AllFLAGS" in args:
            self.flags.update(self.ALL_FLAGS)
        if "UPDATEMACHINE" in args:
            self.updateMachine = True

    def run(self, arglist=[]):
        for flag,flagData in self.flags.iteritems():
            if "seqFile" in flagData:
                seqFile=flagData["seqFile"]
            elif "productType" in flagData or "productVersion" in flagData or "version" in flagData:
                seqFile = self.createTempSeq(**flagData)
            else:
                warning("Unimplemented")
            log("Using Temp Seq File : %s" % seqFile)

            passed = False
            try:
                self.doSequence(seqFileName=seqFile)
                passed = True
            except Exception, e:
                warning(str(e))

            if passed == flagData["isSetIfPass"] and not self.isPropAlreadySet(flag):
                command = "xenrt prop %s add %s" % (self.machineName, flag)
            elif passed != flagData["isSetIfPass"] and self.isPropAlreadySet(flag):
                command = "xenrt prop %s del %s" % (self.machineName, flag)
            else:
                command = "# %s %s flag %s" % (self.machineName,"is already having required" if self.isPropAlreadySet(flag) else "neither need nor has", flag)
            if self.updateMachine:
                xenrt.util.command(command)
                xenrt.util.command("echo \"%s\" >> ~/xenrtautoflagger.log" % command)
            else:
                xenrt.util.command("echo \"%s\" >> ~/xenrt_autoflag_pending" % command)
