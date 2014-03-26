import xenrt
import string, xmlrpclib, IPy, httplib, socket, sys, traceback, os, re, bz2
from xenrt.lib.opsys import OS, registerOS
from zope.interface import implements

__all__ = ["WindowsOS"]

class MyHTTPConnection(httplib.HTTPConnection):
    XENRT_SOCKET_TIMEOUT = 600
    
    def connect(self):
        """Connect to the host and port specified in __init__."""
        self.timeout =  self.XENRT_SOCKET_TIMEOUT
        self.sock = socket.create_connection((self.host, self.port),
                                             self.timeout)
        if self._tunnel_host:
            self._tunnel()

class MyReallyImpatientHTTPConnection(MyHTTPConnection):
    XENRT_SOCKET_TIMEOUT = 5

class MyImpatientHTTPConnection(MyHTTPConnection):
    XENRT_SOCKET_TIMEOUT = 30

class MyPatientHTTPConnection(MyHTTPConnection):
    XENRT_SOCKET_TIMEOUT = 86400

class MyTrans(xmlrpclib.Transport):

    @xenrt.irregularName
    def make_connection(self, host):
        # create a HTTP connection object from a host descriptor
        host, extra_headers, x509 = self.get_host_info(host)
        return MyHTTPConnection(host)

class MyReallyImpatientTrans(xmlrpclib.Transport):

    @xenrt.irregularName
    def make_connection(self, host):
        # create a HTTP connection object from a host descriptor
        host, extra_headers, x509 = self.get_host_info(host)
        return MyReallyImpatientHTTPConnection(host)

class MyImpatientTrans(xmlrpclib.Transport):

    @xenrt.irregularName
    def make_connection(self, host):
        # create a HTTP connection object from a host descriptor
        host, extra_headers, x509 = self.get_host_info(host) 
        return MyImpatientHTTPConnection(host)

class MyPatientTrans(xmlrpclib.Transport):

    @xenrt.irregularName
    def make_connection(self, host):
        # create a HTTP connection object from a host descriptor
        host, extra_headers, x509 = self.get_host_info(host) 
        return MyPatientHTTPConnection(host)


class WindowsOS(OS):

    implements(xenrt.interfaces.InstallMethodIso)

    @staticmethod
    def knownDistro(distro):
        if distro[0] == 'w' or distro[0] == 'v':
            return True
        else:
            return False

    @staticmethod
    def testInit(parent):
        return WindowsOS("win7sp1x86", parent)

    def __init__(self, distro, parent):
        super(self.__class__, self).__init__(parent)

        self.distro = distro
        self.isoRepo = xenrt.IsoRepository.Windows
        self.isoName = "%s.iso" % self.distro
        self.defaultRootdisk = 20 * xenrt.GIGA
        self.vifStem = "eth"
        self.viridian = True

    def waitForInstallCompleteAndFirstBoot(self):
        xenrt.TEC().logverbose("Getting IP address")
        self.parent.getIP(10800)
        xenrt.TEC().logverbose("Got IP, waiting for XML/RPC daemon")
        self.waitForDaemon(14400)
        self.updateDaemon()

    def waitForBoot(self, timeout):
        self.waitForDaemon(timeout)

    def waitForDaemon(self, timeout):
        sleeptime = 15
        now = xenrt.util.timenow()
        deadline = now + timeout
        perrors = 0
        while True:
            xenrt.TEC().logverbose("Checking for exec daemon on %s" %
                                   (self.parent.getIP()))
            try:
                if self._xmlrpc(impatient=True).isAlive():
                    xenrt.TEC().logverbose(" ... OK reply from %s" %
                                           (self.parent.getIP()))
                    return xenrt.RC_OK
            except socket.error, e:
                xenrt.TEC().logverbose(" ... %s" % (str(e)))
            except socket.timeout, e:
                xenrt.TEC().logverbose(" ... %s" % (str(e)))
            except xmlrpclib.ProtocolError, e:
                perrors = perrors + 1
                if perrors >= 3:
                    raise
                xenrt.TEC().warning("XML-RPC daemon ProtocolError during "
                                    "poll (%s)" % (str(e)))
            now = xenrt.util.timenow()
            if now > deadline:
                raise xenrt.XRTFailure("Waiting for XML/RPC timed out")
            xenrt.sleep(sleeptime, log=False)
   
    def getName(self):
        # Temporary function to ease migration from GenericPlace
        return self.parent.getIP()

    def checkHealth(self, unreachable=False, noreachcheck=False, desc=""):
        # Temporary function to ease migration from GenericPlace
        return

    def _xmlrpc(self, impatient=False, patient=False, reallyImpatient=False):
        if reallyImpatient:
            trans = MyReallyImpatientTrans()
        elif impatient:
            trans = MyImpatientTrans()
        elif patient:
            trans = MyPatientTrans()
        else:
            trans = MyTrans()
            
        ip = IPy.IP(self.parent.getIP())
        url = ""
        if ip.version() == 6:
            url = 'http://[%s]:8936'
        else:
            url = 'http://%s:8936'
        return xmlrpclib.ServerProxy(url % (self.parent.getIP()),
                                     transport=trans, 
                                     allow_none=True)

    def execCmd(self, command, level=xenrt.RC_FAIL, desc="Remote command",
                   returndata=False, returnerror=True, returnrc=False,
                   timeout=300, ignoredata=False, powershell=False,ignoreHealthCheck=False):
        """Execute a command and wait for completion."""
        currentPollPeriod = 1
        maxPollPeriod = 16

        try:
            xenrt.TEC().logverbose("Running on %s via daemon: %s" %
                                   (self.parent.getIP(), command.encode("utf-8")))
            started = xenrt.util.timenow()
            s = self._xmlrpc()
            if powershell:
                ref = s.runpshell(command.encode("utf-16").encode("uu"))
            else:
                ref = s.runbatch(command.encode("utf-16").encode("uu"))
            xenrt.sleep(currentPollPeriod, log=False)
            errors = 0
            if xenrt.TEC().lookup("EXTRA_TIME", False, boolean=True):
                maxerrors = 6
            else:
                maxerrors = 2
            while True:
                try:
                    st = s.poll(ref)
                    errors = 0
                except socket.error, e:
                    errors = errors + 1
                    if errors > maxerrors:
                        raise
                    st = "ERROR"
                if st == "DONE":
                    break
                if timeout:
                    now = xenrt.util.timenow()
                    deadline = started + timeout
                    if now > deadline:
                        xenrt.TEC().logverbose("Timed out polling for %s on %s"
                                               % (ref, self.parent.getIP()))
                        return xenrt.XRT("%s timed out" % (desc), level)

                if currentPollPeriod < maxPollPeriod:
                    currentPollPeriod *= 2
                    currentPollPeriod = min(currentPollPeriod, maxPollPeriod)

                xenrt.sleep(currentPollPeriod, log=False)
            if not ignoredata:
                data = s.log(ref)
                xenrt.TEC().log(data.encode("utf-8"))
            else:
                data = None
            rc = s.returncode(ref)
            try:
                s.cleanup(ref)
            except Exception, e:
                xenrt.TEC().warning("Got exception while cleaning up after "
                                    "execCmd: %s" % (str(e)))
            if rc != 0 and returnerror:
                return xenrt.XRT("%s returned error (%d)" % (desc, rc),
                                 level,
                                 data)
            if returndata:
                return data
            if returnrc:
                return rc
            return 0
        except xenrt.XRTException, e:
            if not ignoreHealthCheck:
                self.checkHealth()
            raise
        except Exception, e:
            sys.stderr.write(str(e))
            traceback.print_exc(file=sys.stderr)
            if not ignoreHealthCheck:
                self.checkHealth()
            raise

    def startCmd(self, command):
        """Asynchronously start a command"""
        xenrt.TEC().logverbose("Starting on %s via daemon: %s" %
                               (self.parent.getIP(), command.encode("utf-8")))
        try:
            ref = self._xmlrpc().runbatch(command.encode("utf-16").encode("uu"))
            xenrt.TEC().logverbose(" ... started")
            return ref
        except Exception, e:
            self.checkHealth()
            raise
        
    def isDaemonAlive(self):
        """Return True if this place has a reachable XML-RPC test daemon"""
        try:
            if self._xmlrpc().isAlive():
                return True
        except:
            pass
        return False

    def updateDaemon(self):
        """Update the test execution daemon to the latest version"""
        xenrt.TEC().logverbose("Updating XML-RPC daemon on %s" % (self.parent.getIP()))
        f = file("%s/utils/execdaemon.py" %
                 (xenrt.TEC().lookup("LOCAL_SCRIPTDIR")), "r")
        data = f.read()
        f.close()
        try:
            self._xmlrpc().stopDaemon(data)
            try:
                self._xmlrpc().isAlive()
            except:
                pass
            if xenrt.TEC().lookup("EXTRA_TIME", False, boolean=True):
                xenrt.sleep(60)
            else:
                xenrt.sleep(30)
        except Exception, e:
            self.checkHealth()
            raise

    def shutdown(self):
        """Use the test execution daemon to shutdown the guest"""
        xenrt.TEC().logverbose("Shutting down %s" % (self.parent.getIP()))
        self._xmlrpc().shutdown()
        
    def reboot(self):
        """Use the test execution daemon to reboot the guest"""
        xenrt.TEC().logverbose("Rebooting %s" % (self.parent.getIP()))
        self._xmlrpc().reboot()

    def pollCmd(self, ref, retries=1):
        """Returns True if the command has completed."""
        try:
            while retries > 0:
                try:
                    retries = retries - 1
                    st = self._xmlrpc().poll(ref)
                    break
                except Exception, e:
                    if retries == 0:
                        raise
                    xenrt.sleep(15)
            if st == "DONE":
                return True
            return False
        except Exception, e:
            self.checkHealth()
            raise

    def getCmdPID(self, ref):
        """Returns the PID of the command"""
        try:
            return self._xmlrpc().getPID(ref)
        except Exception, e:
            self.checkHealth()
            raise

    def createDir(self, pathname):
        xenrt.TEC().logverbose("CreateDir %s on %s" % (pathname, self.parent.getIP()))
        try:
            self._xmlrpc().createDir(pathname)
        except Exception, e:
            self.checkHealth()
            raise

    def cmdReturnCode(self, ref):
        """Returns the return code of the command."""
        try:
            return int(self._xmlrpc().returncode(ref))
        except Exception, e:
            self.checkHealth()
            raise

    def cmdCleanup(self, ref):
        """Clean up the state for a command"""
        try:
            self._xmlrpc().cleanup(ref)
        except Exception, e:
            self.checkHealth()
            raise

    def cmdLog(self, ref):
        """Return the logfile text from a command."""
        try:
            return self._xmlrpc().log(ref).encode("utf-8")
        except Exception, e:
            self.checkHealth()
            raise
        
    def cmdWait(self, ref, level=xenrt.RC_FAIL, desc="Remote command",
                   returndata=False, timeout=None, cleanup=True):
        """Wait for completion of a command started with xmlrpcStart."""
        try:
            started = xenrt.util.timenow()
            s = self._xmlrpc()
            while True:
                st = s.poll(ref)
                if st == "DONE":
                    break
                if timeout:
                    now = xenrt.util.timenow()
                    deadline = started + timeout
                    if now > deadline:
                        return xenrt.XRT("%s timed out" % (desc), level)
                xenrt.sleep(15)
            data = s.log(ref).encode("utf-8")
            xenrt.TEC().log(data)
            rc = s.returncode(ref)
            if cleanup:
                s.cleanup(ref)
            if rc != 0:
                return xenrt.XRT("%s returned error (%d)" % (desc, rc),
                                 level,
                                 data)
            if returndata:
                return data
            return 0
        except Exception, e:
            self.checkHealth()
            raise
    
    def getTime(self):
        xenrt.TEC().logverbose("GetTime on %s" % (self.parent.getIP()))
        try:
            t = self._xmlrpc().getTime()
            xenrt.TEC().logverbose("GetTime on %s returned %s" %
                                   (self.parent.getIP(), str(t)))
            return t
        except Exception, e:
            self.checkHealth()
            raise
    
    def getEnvVar(self, var):
        xenrt.TEC().logverbose("GetEnvVar %s on %s" % (var, self.parent.getIP()))
        try:
            return self._xmlrpc().getEnvVar(var)
        except Exception, e:
            self.checkHealth()
            raise
 
    def unpackTarball(self, tarball, dest, patient=False):
        xenrt.TEC().logverbose("UnpackTarball %s to %s on %s" %
                               (tarball, dest, self.parent.getIP()))
        try:
            return self._xmlrpc(patient=patient).unpackTarball(tarball, dest)
        except Exception, e:
            self.checkHealth()
            raise
    
    def tempDir(self, suffix="", prefix="", path=None, patient=False):
        xenrt.TEC().logverbose("TempDir on %s" % (self.parent.getIP()))
        try:
            if path:
                return self._xmlrpc(patient=patient).tempDir(suffix, prefix, path)
            else:
                return self._xmlrpc(patient=patient).tempDir(suffix, prefix)
        except Exception, e:
            self.checkHealth()
            raise

    def checkOtherDaemon(self, ip):
        try:
            return self._xmlrpc().checkOtherDaemon(ip)
        except Exception, e:
            self.checkHealth()
            raise

    def killAll(self, name):
        xenrt.TEC().logverbose("KillAll %s on %s" % (name, self.parent.getIP()))
        try:
            return self._xmlrpc().killall(name)
        except Exception, e:
            self.checkHealth()
            raise

    def killProcess(self, pid):
        xenrt.TEC().logverbose("Kill %s on %s" % (pid, self.parent.getIP()))
        try:
            return self._xmlrpc().kill(pid)
        except Exception, e:
            self.checkHealth()
            raise

    def processList(self):
        xenrt.TEC().logverbose("PS on %s" % (self.parent.getIP()))
        numberOfTimes = 5
        while True:
            try:
                return self._xmlrpc().ps()
            except Exception, e:
                if numberOfTimes > 0:
                    xenrt.TEC().logverbose("ps() call to the guest failed. Trying again.")
                    numberOfTimes -= 1
                    xenrt.sleep(60)
                else:
                    self.checkHealth()
                    raise
    
    def isBigDumpPresent(self, ignoreHealthCheck=False):
        xenrt.TEC().logverbose("Bugdump on %s" % (self.parent.getIP()))
        try:
            s = self._xmlrpc()
            if s.globpath("%s\\MEMORY.DMP" % s.getEnvVar("SystemRoot")):
                return True
            else:
                return False
        except Exception, e:
            if not ignoreHealthCheck:
                self.checkHealth()
            raise
    
    def sha1Sum(self, filename, patient=False):
        xenrt.TEC().logverbose("Sha1Sum on %s" % (self.parent.getIP()))
        try:
            return self._xmlrpc(patient=patient).sha1Sum(filename)
        except Exception, e:
            self.checkHealth()
            raise

    def sha1Sums(self, temp, list, patient=False):
        xenrt.TEC().logverbose("Sha1Sums on %s" % (self.parent.getIP()))
        try:
            return self._xmlrpc(patient=patient).sha1Sums(temp, list)
        except Exception, e:
            self.checkHealth()
            raise

    def dirRights(self, dir, patient=False):
        xenrt.TEC().logverbose("DirRights %s on %s" % (dir, self.parent.getIP()))
        try:
            return self._xmlrpc(patient=patient).dirRights(dir)
        except Exception, e:
            self.checkHealth()
            raise

    def delTree(self, dir, patient=False):
        xenrt.TEC().logverbose("DelTree %s on %s" % (dir, self.parent.getIP()))
        try:
            return self._xmlrpc(patient=patient).deltree(dir)
        except Exception, e:
            self.checkHealth()
            raise

    def listMiniDumpss(self, ignoreHealthCheck=False):
        xenrt.TEC().logverbose("Minidumps on %s" % (self.parent.getIP()))
        try:
            s = self._xmlrpc()
            return s.globpath("%s\\Minidump\\*" % s.getEnvVar("SystemRoot"))
        except Exception, e:
            if not ignoreHealthCheck:
                self.checkHealth()
            raise
        
    def readFile(self, filename, patient=False, ignoreHealthCheck=False):
        try:
            xenrt.TEC().logverbose("Fetching file %s from %s via daemon" %
                                   (filename, self.parent.getIP()))
            s = self._xmlrpc(patient=patient)
            return s.readFile(filename).data
        except Exception, e:
            if not ignoreHealthCheck:
                self.checkHealth()
            raise

    def getFile(self, remotefn, localfn, patient=False, ignoreHealthCheck=False):
        xenrt.TEC().logverbose("GetFile %s to %s on %s" %
                               (remotefn, localfn, self.parent.getIP()))
        try:
            data = self.readFile(remotefn, patient=patient, ignoreHealthCheck=ignoreHealthCheck)
            f = file(localfn, "w")
            f.write(data)
            f.close()
        except Exception, e:
            if not ignoreHealthCheck:
                self.checkHealth()
            raise

    def getFile2(self, remotefn, localfn, patient=False):
        xenrt.TEC().logverbose("GetFile2 %s to %s on %s" %
                               (remotefn, localfn, self.parent.getIP()))
        try:
            s = self._xmlrpc(patient=patient)
            databz2 = s.readFileBZ2(remotefn).data
            c = bz2.BZ2Decompressor()
            f = file(localfn, "w")
            start = 0
            while True:
                data = c.decompress(databz2[start:start+4096])
                if len(data) > 0:
                    f.write(data)
                start = start + 4096
                if start >= len(databz2):
                    break
            f.close()
        except Exception, e:
            self.checkHealth()
            raise

    def fetchFile(self, url, remotefn):
        try:
            xenrt.TEC().logverbose("Fetching %s to %s on %s via daemon" %
                                   (url,remotefn,self.parent.getIP()))
            s = self._xmlrpc()
            return s.fetchFile(url, remotefn)
        except Exception, e:
            self.checkHealth()
            raise

    def daemonVersion(self):
        s = self._xmlrpc()
        try:
            return s.version()
        except Exception, e:
            self.checkHealth()
            raise

    def windowsVersion(self):
        xenrt.TEC().logverbose("WindowsVersion on %s" % (self.parent.getIP()))
        try:
            v = self._xmlrpc().windowsVersion()
            xenrt.TEC().logverbose("WindowsVersion returned %s" % str(v))
            return v
        except Exception, e:
            self.checkHealth()
            raise

    def getArch(self):
        xenrt.TEC().logverbose("GetArch on %s" % (self.parent.getIP()))
        try:
            return self._xmlrpc().getArch()
        except Exception, e:
            self.checkHealth()
            raise
    
    def getCPUs(self):
        xenrt.TEC().logverbose("GetCPUs on %s" % (self.parent.getIP()))
        patient = xenrt.TEC().lookup("EXTRA_TIME", False, boolean=True) 
        try:
            return self._xmlrpc(patient=patient).getCPUs()
        except Exception, e:
            self.checkHealth()
            raise

    def getSockets(self):
        """ Get the number of CPU sockets (filled) on the remote system """
        if float(self.windowsVersion()) < 6.0:
            raise xenrt.XRTError("N/A for NT kernel < 6.0")
        xenrt.TEC().logverbose("GetSockets on %s" % (self.parent.getIP()))
        patient = xenrt.TEC().lookup("EXTRA_TIME", False, boolean=True)
        try:
            return self._xmlrpc(patient=patient).getSockets()
        except Exception, e:
            self.checkHealth()
            raise

    def getCPUCores(self):
        """ Get the number of cores on each physical CPU on the remote system """
        if float(self.windowsVersion()) < 6.0:
            raise xenrt.XRTError("N/A for NT kernel < 6.0")
        xenrt.TEC().logverbose("GetCPUCores on %s" % (self.parent.getIP()))
        patient = xenrt.TEC().lookup("EXTRA_TIME", False, boolean=True) 
        try:
            return self._xmlrpc(patient=patient).getCPUCores()
        except Exception, e:
            self.checkHealth()
            raise

    def getCPUvCPUs(self):
        """ Get the number of logical CPUs on each physical CPU on the remote system """
        if float(self.windowsVersion()) < 6.0:
            raise xenrt.XRTError("N/A for NT kernel < 6.0")
        xenrt.TEC().logverbose("GetCPUVCPUs on %s" % (self.parent.getIP()))
        patient = xenrt.TEC().lookup("EXTRA_TIME", False, boolean=True) 
        try:
            return self._xmlrpc(patient=patient).getCPUVCPUs()
        except Exception, e:
            self.checkHealth()
            raise
    
    def partition(self, disk):
        xenrt.TEC().logverbose("Partition %s on %s" % (disk, self.parent.getIP()))
        try:
            return self._xmlrpc().partition(disk)
        except Exception, e:
            self.checkHealth()
            raise

    def deletePartition(self, letter):
        xenrt.TEC().logverbose("DeletePartition %s on %s" %
                               (letter, self.parent.getIP()))
        try:
            return self._xmlrpc().deletePartition(letter)
        except Exception, e:
            self.checkHealth()
            raise
   
    def assignDisk(self, disk):
        xenrt.TEC().logverbose("Assign %s on %s" % (disk, self.parent.getIP()))
        try:
            return self._xmlrpc().assign(disk)
        except Exception, e:
            self.checkHealth()
            raise

    def listDisks(self):
        xenrt.TEC().logverbose("ListDisks on %s" % (self.parent.getIP()))
        try:
            return self._xmlrpc().listDisks()
        except Exception, e:
            self.checkHealth()
            raise

    def markDiskOnline(self, diskid=None):
        """ mark disk online by diskid. The function will fail if the diskid is
        invalid or the disk is already online . When diskid == None (default),
        the function will mark any offline disk as online.
        """
        xenrt.TEC().logverbose("Mark disk %s online" % (diskid or "all"))
        data = self.execCmd("echo list disk | diskpart",
                               returndata=True)
        offline = re.findall("Disk\s+([0-9]+)\s+Offline", data)
        if diskid:
            if diskid in offline:
                offline = [ diskid ]
            else:
                raise xenrt.XRTException("disk %d is already online" % diskid)
        for o in offline:
            self.writeFile("c:\\online.txt",
                                 "select disk %s\n"
                                 "attributes disk clear readonly\n"
                                 "online disk noerr" % (o))
            self.execCmd("diskpart /s c:\\online.txt")
    
        
    def formatDisk(self, letter, fstype="ntfs", timeout=1200, quick=False):
        cmd = self.windowsVersion() == "5.0" \
              and "echo y | format %s: /fs:%s" \
              or "format %s: /fs:%s /y"
        cmd = quick and cmd + " /q" or cmd
        self.execCmd(cmd % (letter, fstype), timeout=timeout)
   
    def sendFile(self, localfilename, remotefilename, usehttp=None, ignoreHealthCheck=False):
        if usehttp == None:
            # If the file is larger than 4MB default to using HTTP fetch,
            # otherwise default to XML-RPC push
            if os.stat(localfilename).st_size > 4194304:
                usehttp = True
            else:
                usehttp = False
        try:
            s = self._xmlrpc()
            if usehttp:
                # Pull the file into the guest
                wdir = xenrt.resources.WebDirectory()
                try:
                    wdir.copyIn(localfilename)
                    xenrt.TEC().logverbose("Pulling %s into %s:%s" %
                                           (localfilename,
                                            self.parent.getIP(),
                                            remotefilename))
                    s.fetchFile(wdir.getURL(os.path.basename(localfilename)),
                                remotefilename)
                finally:
                    wdir.remove()
            else:
                # Push the file to the guest
                f = file(localfilename, 'r')
                data = f.read()
                f.close()
                xenrt.TEC().logverbose("Pushing %s to %s:%s" %
                                       (localfilename,
                                        self.parent.getIP(),
                                        remotefilename))
                s.createFile(remotefilename, xmlrpclib.Binary(data))
        except Exception, e:
            if not ignoreHealthCheck:
                self.checkHealth()
            raise

    def writeFile(self, filename, data):
        try:
            xenrt.TEC().logverbose("Writing file %s to %s via daemon" %
                                   (filename, self.parent.getIP()))
            s = self._xmlrpc()
            s.createFile(filename, xmlrpclib.Binary(data))
        except Exception, e:
            self.checkHealth()
            raise

    def sendTarball(self, localfilename, remotedirectory):
        xenrt.TEC().logverbose("SendTarball %s to %s on %s" %
                               (localfilename, remotedirectory, self.parent.getIP()))
        try:
            s = self._xmlrpc()
            f = file(localfilename, 'r')
            data = f.read()
            f.close()
            s.pushTarball(xmlrpclib.Binary(data), remotedirectory)
        except Exception, e:
            self.checkHealth()
            raise

    def pushTarball(self, data, directory):
        xenrt.TEC().logverbose("PushTarball to %s on %s" %
                               (directory, self.parent.getIP()))
        try:
            return self._xmlrpc().pushTarball(data, directory)
        except Exception, e:
            self.checkHealth()
            raise

    def sendRecursive(self, localdirectory, remotedirectory):
        xenrt.TEC().logverbose("SendRecursive %s to %s on %s" %
                               (localdirectory, remotedirectory, self.parent.getIP()))
        try:
            f = xenrt.TEC().tempFile()
            xenrt.util.command("tar -zcf %s -C %s ." % (f, localdirectory))
            self.sendTarball(f, remotedirectory)
            os.unlink(f)
        except Exception, e:
            self.checkHealth()
            raise

    def fetchRecursive(self, remotedirectory, localdirectory, ignoreHealthCheck=False):
        xenrt.TEC().logverbose("FetchRecursive %s to %s on %s" %
                               (remotedirectory, localdirectory, self.parent.getIP()))
        try:
            f = xenrt.TEC().tempFile()
            rf = self._xmlrpc().tempFile()
            self._xmlrpc().createTarball(rf, remotedirectory)
            self.getFile(rf, f, ignoreHealthCheck=ignoreHealthCheck)
            xenrt.util.command("tar -xf %s -C %s" % (f, localdirectory))
            self.removeFile(rf, ignoreHealthCheck=ignoreHealthCheck)
            os.unlink(f)
        except Exception, e:
            if not ignoreHealthCheck:
                self.checkHealth()
            raise

    def extractTarball(self, filename, directory, patient=True):
        xenrt.TEC().logverbose("ExtractTarball %s to %s on %s" %
                               (filename, directory, self.parent.getIP()))
        try:
            self._xmlrpc(patient=patient).extractTarball(filename, directory)
        except Exception, e:
            self.checkHealth()
            raise

    def globPath(self, p):
        xenrt.TEC().logverbose("GlobPath %s on %s" % (p, self.parent.getIP()))
        try:
            return self._xmlrpc().globpath(p)
        except Exception, e:
            self.checkHealth()
            raise

    def globPattern(self, pattern):
        xenrt.TEC().logverbose("GlobPattern %s on %s" % (pattern, self.parent.getIP()))
        try:
            return self._xmlrpc().globPattern(pattern)
        except Exception, e:
            self.checkHealth()
            raise

    def fileExists(self, filename, patient=False, ignoreHealthCheck=False):
        xenrt.TEC().logverbose("FileExists %s on %s" % (filename, self.parent.getIP()))
        try:
            ret = self._xmlrpc(patient=patient).fileExists(filename)
            xenrt.TEC().logverbose("FileExists returned %s" % str(ret))
            return ret
        except Exception, e:
            if not ignoreHealthCheck:
                self.checkHealth()
            raise

    def dirExists(self, filename, patient=False):
        xenrt.TEC().logverbose("DirExists %s on %s" % (filename, self.parent.getIP()))
        try:
            return self._xmlrpc(patient=patient).dirExists(filename)
        except Exception, e:
            self.checkHealth()
            raise

    def fileMTime(self, filename, patient=False):
        xenrt.TEC().logverbose("FileMTime %s on %s" % (filename, self.parent.getIP()))
        try:
            return self._xmlrpc(patient=patient).fileMTime(filename)
        except Exception, e:
            self.checkHealth()
            raise

    def diskInfo(self):
        xenrt.TEC().logverbose("DiskInfo on %s" % (self.parent.getIP()))
        try:
            return self._xmlrpc().diskInfo()
        except Exception, e:
            self.checkHealth()
            raise
    
    def doSysprep(self):
        xenrt.TEC().logverbose("Sysprep on %s" % (self.parent.getIP()))
        try:
            return self._xmlrpc().doSysprep()
        except Exception, e:
            self.checkHealth()
            raise

    def getRootDisk(self):
        xenrt.TEC().logverbose("GetRootDisk on %s" % (self.parent.getIP()))
        try:
            return self._xmlrpc().getRootDisk()
        except Exception, e:
            self.checkHealth()
            raise
    
    def createFile(self, filename, data):
        xenrt.TEC().logverbose("CreateFile %s on %s" % (filename, self.parent.getIP()))
        try:
            return self._xmlrpc().createFile(filename, data)
        except Exception, e:
            self.checkHealth()
            raise
        
    def removeFile(self, filename, patient=False, ignoreHealthCheck=False):
        xenrt.TEC().logverbose("RemoveFile %s on %s" % (filename, self.parent.getIP()))
        try:
            return self._xmlrpc(patient=patient).removeFile(filename)
        except Exception, e:
            if not ignoreHealthCheck:
                self.checkHealth()
            raise

    def createEmptyFile(self, filename, size):
        xenrt.TEC().logverbose("CreateEmptyFile %s on %s" %
                               (filename, self.parent.getIP()))
        try:
            return self._xmlrpc().createEmptyFile(filename, size)
        except Exception, e:
            self.checkHealth()
            raise
    
    def addBootFlag(self, flag):
        xenrt.TEC().logverbose("AddBootFlag %s on %s" % (flag, self.parent.getIP()))
        try:
            return self._xmlrpc().addBootFlag(flag)
        except Exception, e:
            self.checkHealth()
            raise

    def appActivate(self, app):
        xenrt.TEC().logverbose("AppActivate %s on %s" % (app, self.parent.getIP()))
        try:
            return self._xmlrpc().appActivate(app)
        except Exception, e:
            self.checkHealth()
            raise

    def sendKeys(self, keys):
        xenrt.TEC().logverbose("SendKeys %s on %s" % (keys, self.parent.getIP()))
        try:
            return self._xmlrpc().sendKeys(keys)
        except Exception, e:
            self.checkHealth()
            raise

    def getWindowsEventLog(self, log, clearlog=False, ignoreHealthCheck=False):
        """Return a string containing a CSV dump of the specified Windows
        event log."""
        if not self.fileExists("c:\\psloglist.exe", ignoreHealthCheck=ignoreHealthCheck):
            self.sendFile("%s/distutils/psloglist.exe" %
                                (xenrt.TEC().lookup("LOCAL_SCRIPTDIR")),
                                "c:\\psloglist.exe", ignoreHealthCheck=ignoreHealthCheck)
        command = []
        command.append("c:\\psloglist.exe")
        command.append("/accepteula")
        command.append("-s")
        command.append("-x %s" % (log))
        if clearlog:
            command.append("-c")
        data = self.execCmd(string.join(command),
                               returndata=True,
                               timeout=3600, ignoreHealthCheck=ignoreHealthCheck)
        return data

    def getWindowsEventLogs(self, logdir, ignoreHealthCheck=False):
        """Fetch all useful Windows event logs to CSV files in the specified
        directory."""
        clearlog = xenrt.TEC().lookup("CLEAR_EVENT_LOGS_ON_FETCH",
                                      False,
                                      boolean=True)
        for log in ("system", "application", "security"):
            # TODO Add mechanism for excluding log collection
            #if self.logFetchExclude and log in self.logFetchExclude:
            #    continue
            data = self.getWindowsEventLog(log, clearlog=clearlog, ignoreHealthCheck=ignoreHealthCheck)
            f = file("%s/%s.csv" % (logdir, log), "w")
            f.write(data)
            f.close()

    def winRegLookup(self, hive, key, name, healthCheckOnFailure=True, suppressLogging=False):
        """Look up a Windows registry value."""
        
        if not suppressLogging:
            xenrt.TEC().logverbose("Registry lookup: %s %s %s" % (hive, key, name))
        try:
            s = self._xmlrpc()
            val = s.regLookup(hive, key, name)
            if not suppressLogging:
                xenrt.TEC().logverbose("Registry lookup returned: " + str(val))
            return val
        except Exception, e:
            if not suppressLogging:
                xenrt.TEC().logverbose("Registry key not found: " + str(e))
            if healthCheckOnFailure:
                self.checkHealth()
            raise

    def winRegAdd(self, hive, key, name, vtype, value):
        """Add a value to the Windows registry"""
        xenrt.TEC().logverbose("Registry add on %s %s:%s %s=%s (%s)" %
                               (self.parent.getIP(), hive, key, name, value, vtype))
        try:
            s = self._xmlrpc()
            s.regSet(hive, key, name, vtype, value)
        except Exception, e:
            self.checkHealth()
            raise

    def winRegDel(self, hive, key, name, ignoreHealthCheck=False):
        """Remove a value from the Windows registry"""
        xenrt.TEC().logverbose("Registry delete on %s %s:%s %s" %
                               (self.parent.getIP(), hive, key, name))
        try:
            s = self._xmlrpc()
            s.regDelete(hive, key, name)
        except Exception, e:
            if not ignoreHealthCheck:
                self.checkHealth()
            raise

    def disableReceiverMaxProto(self):
        
        try:
            self.winRegDel("HKLM", "SYSTEM\\CurrentControlSet\\services\\xenvif\\Parameters", "ReceiverMaximumProtocol")
        except:
            xenrt.TEC().logverbose("winRegDel fails post Clearwater")
            
        self.winRegAdd("HKLM", "SYSTEM\\CurrentControlSet\\services\\xenvif\\Parameters", "ReceiverMaximumProtocol", "DWORD", 0)
        
    def getReceiverMaxProtocol(self):
        
        return self.winRegLookup('HKLM', 'SYSTEM\\CurrentControlSet\\services\\xenvif\\Parameters', 'ReceiverMaximumProtocol')

    def configureAutoLogon(self, user):
        if not user.password:
            user.password = xenrt.TEC().lookup(["WINDOWS_INSTALL_ISOS",
                                                "ADMINISTRATOR_PASSWORD"],
                                                "xensource")
        self.execCmd("cacls c:\\execdaemon.log /E /G %s:F" % (user.name))
        self.execCmd("cacls c:\\execdaemon.py /E /G %s:F" % (user.name))
        # Give everyone read-write permissions for the auto-logon keys.
        t = self.tempDir()
        self.writeFile("%s\\regperm.txt" % (t), 
                             "\\Registry\\Machine\\software\\microsoft\\windows nt\\"
                             "currentversion\\winlogon [1 5 9]")
        self.execCmd("regini %s\\regperm.txt" % (t))
        self.delTree(t)
        self.winRegAdd("HKLM", 
                       "software\\microsoft\\windows nt\\currentversion\\winlogon",
                       "DefaultUserName",
                       "SZ",
                        user.name)
        self.winRegAdd("HKLM", 
                       "software\\microsoft\\windows nt\\currentversion\\winlogon",
                       "DefaultPassword",
                       "SZ",
                        user.password)
        self.winRegAdd("HKLM", 
                       "software\\microsoft\\windows nt\\currentversion\\winlogon",
                       "AutoAdminLogon",
                       "SZ",
                       "1")
        self.winRegAdd("HKLM", 
                       "software\\microsoft\\windows nt\\currentversion\\winlogon",
                       "DefaultDomainName",
                       "SZ",
                        user.server.domainname)

    # TODO Add JoinDomain and LeaveDomain in context of new object model - currently very tied to host

registerOS(WindowsOS)
