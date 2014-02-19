import xenrt
import libperf
import string
import time

class TCTimeVMMigrateDowntime(libperf.PerfTestCase):

    def __init__(self):
        libperf.PerfTestCase.__init__(self, "TCTimeVMMigrateDowntime")
        self.vm = None

        # Parameters that can be overridden via <arg>s in sequence files
        self.vmname = None
        self.vmimage = None
        self.numiters = 100
        self.useImportedVM = False

    def prepare(self, arglist=None):
        # Parse generic args
        self.parseArgs(arglist)

        # Parse args relating to this test
        for arg in arglist:
            l = string.split(arg, "=", 1)
            if l[0] == 'guest':
                self.vmname = l[1]
            elif l[0] == 'vmimage':
                self.vmimage = l[1]
            elif l[0] == 'numiters':
                self.numiters = int(l[1])
            elif l[0] == 'useimportedvm':
                self.useImportedVM = True

        self.initialiseHostList()
        self.configureAllHosts()

        # Use local storage
        sruuid = self.host.execdom0("xe sr-list 'name-label=Local storage' host=%s params=uuid --minimal" % self.host.getName()).strip()
        xenrt.TEC().logverbose("sruuid of local storage is %s" % sruuid)

    def prepareVM(self):
        if self.useImportedVM:
            # Get a handle on local storage
            sruuid = self.host.getLocalSR()

            # Import the VM
            xenrt.TEC().logverbose("importing VM with name [%s] from image [%s] into SR [%s]" % (self.vmname, self.vmimage, sruuid))
            vm = self.importVMFromRefBase(self.host, self.vmimage, self.vmname, sruuid)

            # Start the VM (will only return when the VM has booted)
            cli = vm.getCLIInstance()
            cli.execute("vm-start", "uuid=\"%s\"" % vm.uuid)

            vm.existing(self.host)

            # Wait for it to start
            time.sleep(90)

            return vm
        else:
            # Get a handle on the guest
            vm = xenrt.TEC().registry.guestGet(self.vmname)
            xenrt.TEC().logverbose("vm with name [%s] is [%s]" % (self.vmname, self.vm))

            # Disable the VM's firewall so it's pingable
            vm.disableFirewall()
            xenrt.TEC().logverbose("disabled firewall in guest")
            return vm

    def run(self, arglist=None):
        self.vm = self.prepareVM()

        # Create a logfile for the downtimes
        migrateLogfile = libperf.createLogName("downtime")
        xenrt.TEC().comment("downtime logfile: %s" % migrateLogfile)

        libperf.outputToResultsFile(migrateLogfile, "# iter	pingable	running total-duration")

        for i in range(0, self.numiters):
            xenrt.TEC().logverbose("migration iteration %d of %d" % (i, self.numiters))
            timesStr = self.timeMigrate()
            line = "%d	%s" % (i, timesStr)
            libperf.outputToResultsFile(migrateLogfile, line)

    def timeMigrate(self):
        # Watch for the downtime in two different ways
        t1 = DowntimeWatcherPing(self, self.host, self.vm)
        t2 = DowntimeWatcherRunning(self, self.host, self.vm)
        watcherThreads = [t1, t2]

        for t in watcherThreads:
            t.start()
        
        # Do a localhost migrate
        output = self.host.execdom0("time xe vm-migrate uuid=%s host-uuid=%s live=%s" % (self.vm.getUUID(), self.host.getMyHostUUID(), "true"))
        xenrt.TEC().logverbose("output: %s" % output) # e.g. '\nreal\t0m10.156s\nuser\t0m0.000s\nsys\t0m0.000s\n'
        totaltimesecs = libperf.parseTimeOutput(output)

        # Wait for the downtime monitors to return
        for t in watcherThreads:
            t.join()

        # Get the downtime from each thread
        times = [t.getTime() for t in watcherThreads]
        # Convert None into "" -- sometimes DowntimeWatcherRunning doesn't set a valid time
        times = ["" if (t is None) else t for t in times]
        # Also include the total time
        times.append(str(totaltimesecs))
        xenrt.TEC().logverbose("times from threads were %s" % times)

        return '	'.join(times)

    def postRun(self):
        self.finishUp()

# Abstract class: subclasses override run() method.
class DowntimeWatcher(xenrt.XRTThread):
    def __init__(self, tc, host, vm):
        xenrt.XRTThread.__init__(self)
        self.time = None
        self.tc = tc
        self.host = host
        self.vm = vm

    def getTime(self):
        return self.time

class DowntimeWatcherPing(DowntimeWatcher):
    def __init__(self, tc, host, vm):
        DowntimeWatcher.__init__(self, tc, host, vm)

    def getVMIP(self):
        # Get the IP address of the VM
        if self.tc.useImportedVM:
            # Get the domid
            domid = self.host.execdom0("list_domains | grep %s | awk -F\| '{print $1}'" % self.vm.getUUID()).strip()
            # Look up the IP address in xenstore
            ip = self.host.execdom0("xenstore-read /local/domain/%s/attr/eth0/ip" % domid).strip()
        else:
            ip = self.vm.getIP()
        return ip

    def run(self):
        ip = self.getVMIP()
        xenrt.TEC().logverbose("IP of %s is %s" % (self.vm, ip))
        
        # Return the number of consecutive pings that were dropped before connection re-establishment
        interval = 0.1 # seconds
        cmd = "ping -i %.1f %s | grep time= | sed 's/icmp_seq=//' | awk '{if (FNR!=$5) { diff=$5-FNR; print diff; exit }}'" % (interval, ip)
        xenrt.TEC().logverbose("cmd is [%s]" % cmd)
        output = self.host.execdom0(cmd)
        xenrt.TEC().logverbose("output is [%s]" % output)

        droppedpings = int(output.strip())
        xenrt.TEC().logverbose("hence number of dropped pings was %d" % droppedpings)

        # Get the last line of the output
        self.time = str(droppedpings * interval)

class DowntimeWatcherRunning(DowntimeWatcher):
    def __init__(self, tc, host, vm):
        DowntimeWatcher.__init__(self, tc, host, vm)

    def run(self):
        # In Orlando, xentop doesn't use VM names, but rather "Domain-<domid>". So find out the domid.
        domid = int(self.host.execdom0("list_domains | grep %s | awk -F\| '{print $1}'" % self.vm.getUUID()).strip())
        alternativeName = "Domain-%d" % domid

        # Kick off a script to monitor the downtime (based on xentop)
        cmd = "xentop -b -d 0 | perl -n -e 'if (/^\s*NAME/) { if ($state && $numvms == 1) { $finish = `date +%%s.%%N`; chop $finish; chop $start; my $diff = $finish - $start; print \"$diff\\n\"; exit } $numvms = 0; } ++$numvms if (/^\s*%s/ || /^\s*%s/); if (/-s----/) { $start = `date +%%s.%%N` if !$state; $state = 1 }'" % (self.vm.getName(), alternativeName)
        xenrt.TEC().logverbose("cmd is [%s]" % cmd)
        output = self.host.execdom0(cmd)
        # warning: output is very large: lots of errors during downtime

        # Get the last line of the output
        self.time = output.strip().split('\n')[-1]
