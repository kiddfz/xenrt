### THIS FILE WAS AUTO-GENERATED BY ./pts-tools.py @ 19/08/11 17:28 ###

import xenrt
import testcases.xenserver.tc.perf.libperf as libperf

PTS_NAME = "pts321_squeeze_x86"

class PhoronixInstall(libperf.PerfTestCase):
    def __init__(self):
        libperf.PerfTestCase.__init__(self, None)
    
    def prepare(self, arglist):
        self.basicPrepare(arglist or [])
    
    def run(self, arglist):
        self.host = self.getDefaultHost()
        localsruuid = self.host.execdom0("""xe sr-list name-label=Local\ storage  --minimal""").strip()
        self.guest = self.importVMFromRefBase(self.host, "t_chengs/%s.xva" % PTS_NAME, PTS_NAME, localsruuid)
        self.guest.start()

class _PhoronixBase(libperf.PerfTestCase):
    """http://www.phoronix-test-suite.com/"""
    
    TESTNAME = None
    TESTARGS = None
    TESTDESC = None
    
    def __init__(self):
        libperf.PerfTestCase.__init__(self, None)
    
    def createTmpSuite(self):
        SUITEDIR = "~/.phoronix-test-suite/test-suites/local/xenrt"
        try:
            self.guest.execguest("rm -r %s" % SUITEDIR)
        except:
            pass
        self.guest.execguest("mkdir -p %s" % SUITEDIR)
        self.guest.execguest("""cat > %s/suite-definition.xml <<EOF
<?xml version="1.0"?>
<PhoronixTestSuite>
  <SuiteInformation>
    <Title>xenrt</Title>
    <Version>1.0.0</Version>
    <TestType>Other</TestType>
    <Description>xenrt temporary suite</Description>
    <Maintainer>pts-tools.sh</Maintainer>
  </SuiteInformation>
  <Execute>
    <Test>%s</Test>
    <Arguments>%s</Arguments>
    <Description>%s</Description>
  </Execute>
</PhoronixTestSuite>
EOF""" % (SUITEDIR, self.TESTNAME, self.TESTARGS, self.TESTDESC), newlineok = True)
    
    def prepare(self, arglist):
        self.basicPrepare(arglist or [])
        
        self.host = self.getDefaultHost()
        self.guest = self.host.getGuest(PTS_NAME)
        
        self.guest.execguest("rm -rf ~/.phoronix-test-suite/test-results/*")
        
        self.createTmpSuite()
        # PTS does not use exit-codes to signify failure -- we have to check the output
        out = self.guest.execguest("phoronix-test-suite install local/xenrt", timeout=20*60)
        # "ERROR: foo"
        # "The following tests failed to install"
        if out.find("ERROR") > -1 or out.find("failed to install") > -1:
            # TODO: something like sftp.copyFrom("install-failed.log", "%s/install-failed.log" % xenrt.TEC().getLogdir())
            raise xenrt.XRTFailure("%s [%s] failed to install" % (self.TESTNAME, self.TESTDESC))
    
    def run(self, arglist):
        # PTS does not use exit-codes to signify failure -- we have to check the output
        out = self.guest.execguest("phoronix-test-suite batch-benchmark local/xenrt", timeout=5*60*60)  # 5hrs should be enough
        # "ERROR: foo"
        # "The following tests failed to properly run"
        if out.find("ERROR") > -1 or out.find("failed to properly run") > -1:
            #self.tec.logverbose(out)
            raise xenrt.XRTFailure("%s [%s] failed to run" % (self.TESTNAME, self.TESTDESC))
    
    def postRun(self):
        # gather result
        src = "%s/composite.xml" % self.guest.execguest("ls -1d ~/.phoronix-test-suite/test-results/* | grep -v pts-results-viewer").strip()
        dest = "%s/composite.xml" % self.tec.getLogdir()
        sftp = self.guest.sftpClient()
        sftp.copyFrom(src, dest)

class TCPTS_himeno_PoissonPressureSolver(_PhoronixBase):
    TESTNAME="pts/himeno-1.0.0"
    TESTDESC="Poisson Pressure Solver"
    TESTARGS=""

class TCPTS_minion_Solitaire(_PhoronixBase):
    TESTNAME="pts/minion-1.2.0"
    TESTDESC="Solitaire"
    TESTARGS="benchmarks/solitaire/solitaire_benchmark_8.minion"

class TCPTS_unpacklinux_linux2632tarbz2(_PhoronixBase):
    TESTNAME="pts/unpack-linux-1.0.0"
    TESTDESC="linux-2.6.32.tar.bz2"
    TESTARGS=""

class TCPTS_compilebench_TestInitialCreate(_PhoronixBase):
    TESTNAME="pts/compilebench-1.0.0"
    TESTDESC="Test: Initial Create"
    TESTARGS="INITIAL_CREATE"

class TCPTS_stream_TypeCopy(_PhoronixBase):
    TESTNAME="pts/stream-1.1.0"
    TESTDESC="Type: Copy"
    TESTARGS="Copy"

class TCPTS_stream_Scale(_PhoronixBase):
    TESTNAME="pts/stream-1.1.0"
    TESTDESC="Scale"
    TESTARGS="Scale"

class TCPTS_stream_TypeTriad(_PhoronixBase):
    TESTNAME="pts/stream-1.1.0"
    TESTDESC="Type: Triad"
    TESTARGS="Triad"

class TCPTS_stream_TypeAdd(_PhoronixBase):
    TESTNAME="pts/stream-1.1.0"
    TESTDESC="Type: Add"
    TESTARGS="Add"

class TCPTS_stream_TypeScale(_PhoronixBase):
    TESTNAME="pts/stream-1.1.0"
    TESTDESC="Type: Scale"
    TESTARGS="Scale"

class TCPTS_stream_Add(_PhoronixBase):
    TESTNAME="pts/stream-1.1.0"
    TESTDESC="Add"
    TESTARGS="Add"

class TCPTS_stream_Copy(_PhoronixBase):
    TESTNAME="pts/stream-1.1.0"
    TESTDESC="Copy"
    TESTARGS="Copy"

class TCPTS_ffmpeg_AVIToNTSCVCD(_PhoronixBase):
    TESTNAME="pts/ffmpeg-1.5.0"
    TESTDESC="AVI To NTSC VCD"
    TESTARGS=""

class TCPTS_buildapache_TimeToCompile(_PhoronixBase):
    TESTNAME="pts/build-apache-1.4.0"
    TESTDESC="Time To Compile"
    TESTARGS=""

class TCPTS_gnupg_1GBFileEncryption(_PhoronixBase):
    TESTNAME="pts/gnupg-1.3.1"
    TESTDESC="1GB File Encryption"
    TESTARGS=""

class TCPTS_compresslzma_256MBFileCompression(_PhoronixBase):
    TESTNAME="pts/compress-lzma-1.2.0"
    TESTDESC="256MB File Compression"
    TESTARGS=""

class TCPTS_iozone_Size4GBDiskTestWritePerformance(_PhoronixBase):
    TESTNAME="pts/iozone-1.7.0"
    TESTDESC="Size: 4GB - Disk Test: Write Performance"
    TESTARGS="-r 4k -s 4096M -i0"

class TCPTS_iozone_8GBWritePerformance(_PhoronixBase):
    TESTNAME="pts/iozone-1.7.0"
    TESTDESC="8GB Write Performance"
    TESTARGS="-r 4k -s 8192M -i0"

class TCPTS_iozone_8GBReadPerformance(_PhoronixBase):
    TESTNAME="pts/iozone-1.7.0"
    TESTDESC="8GB Read Performance"
    TESTARGS="-r 4k -s 8192M -i0 -i1"

class TCPTS_iozone_Size4GBDiskTestReadPerformance(_PhoronixBase):
    TESTNAME="pts/iozone-1.7.0"
    TESTDESC="Size: 4GB - Disk Test: Read Performance"
    TESTARGS="-r 4k -s 4096M -i0 -i1"

class TCPTS_gmpbench_TotalTime(_PhoronixBase):
    TESTNAME="pts/gmpbench-1.0.1"
    TESTDESC="Total Time"
    TESTARGS=""

class TCPTS_aiostress_RandomWrite(_PhoronixBase):
    TESTNAME="pts/aio-stress-1.1.0"
    TESTDESC="Random Write"
    TESTARGS="-o 2"

class TCPTS_fsmark_1000Files1MBSize(_PhoronixBase):
    TESTNAME="pts/fs-mark-1.0.0"
    TESTDESC="1000 Files, 1MB Size"
    TESTARGS="-s 1048576 -n 1000"

class TCPTS_sudokut_TotalTime(_PhoronixBase):
    TESTNAME="pts/sudokut-1.0.0"
    TESTDESC="Total Time"
    TESTARGS=""

class TCPTS_buildmplayer_TimeToCompile(_PhoronixBase):
    TESTNAME="pts/build-mplayer-1.3.0"
    TESTDESC="Time To Compile"
    TESTARGS=""

class TCPTS_compressgzip_2GBFileCompression(_PhoronixBase):
    TESTNAME="pts/compress-gzip-1.1.0"
    TESTDESC="2GB File Compression"
    TESTARGS=""

class TCPTS_sqlite_12500INSERTs(_PhoronixBase):
    TESTNAME="pts/sqlite-1.8.0"
    TESTDESC="12,500 INSERTs"
    TESTARGS=""

class TCPTS_dcraw_RAWToPPMImageConversion(_PhoronixBase):
    TESTNAME="pts/dcraw-1.0.0"
    TESTDESC="RAW To PPM Image Conversion"
    TESTARGS=""

class TCPTS_buildlinuxkernel_TimeToCompile(_PhoronixBase):
    TESTNAME="pts/build-linux-kernel-1.2.0"
    TESTDESC="Time To Compile"
    TESTARGS=""

class TCPTS_phpbench_PHPBenchmarkSuite(_PhoronixBase):
    TESTNAME="pts/phpbench-1.0.0"
    TESTDESC="PHP Benchmark Suite"
    TESTARGS=""

class TCPTS_apache_StaticWebPageServing(_PhoronixBase):
    TESTNAME="pts/apache-1.3.0"
    TESTDESC="Static Web Page Serving"
    TESTARGS=""

class TCPTS_mencoder_AVIToLAVC(_PhoronixBase):
    TESTNAME="pts/mencoder-1.3.0"
    TESTDESC="AVI To LAVC"
    TESTARGS=""

class TCPTS_encodeogg_WAVToOgg(_PhoronixBase):
    TESTNAME="pts/encode-ogg-1.2.0"
    TESTDESC="WAV To Ogg"
    TESTARGS=""

class TCPTS_dbench_1Clients(_PhoronixBase):
    TESTNAME="pts/dbench-1.0.0"
    TESTDESC="1 Clients"
    TESTARGS="1"

class TCPTS_dbench_48Clients(_PhoronixBase):
    TESTNAME="pts/dbench-1.0.0"
    TESTDESC="48 Clients"
    TESTARGS="48"

class TCPTS_dbench_12Clients(_PhoronixBase):
    TESTNAME="pts/dbench-1.0.0"
    TESTDESC="12 Clients"
    TESTARGS="12"

class TCPTS_dbench_128Clients(_PhoronixBase):
    TESTNAME="pts/dbench-1.0.0"
    TESTDESC="128 Clients"
    TESTARGS="128"

class TCPTS_openssl_RSA4096bitPerformance(_PhoronixBase):
    TESTNAME="pts/openssl-1.5.0"
    TESTDESC="RSA 4096-bit Performance"
    TESTARGS=""

class TCPTS_tiobench_64MBRandomRead32Threads(_PhoronixBase):
    TESTNAME="pts/tiobench-1.1.0"
    TESTDESC="64MB Random Read - 32 Threads"
    TESTARGS="-k2 -k1 -f 64 -t 32"

class TCPTS_tiobench_64MBRandomWrite32Threads(_PhoronixBase):
    TESTNAME="pts/tiobench-1.1.0"
    TESTDESC="64MB Random Write - 32 Threads"
    TESTARGS="-k3 -k2 -f 64 -t 32"

class TCPTS_byte_Dhrystone2(_PhoronixBase):
    TESTNAME="pts/byte-1.1.0"
    TESTDESC="Dhrystone 2"
    TESTARGS="TEST_DHRY2"

class TCPTS_cray_TotalTime(_PhoronixBase):
    TESTNAME="pts/c-ray-1.0.0"
    TESTDESC="Total Time"
    TESTARGS=""

class TCPTS_espeak_TextToSpeechSynthesis(_PhoronixBase):
    TESTNAME="pts/espeak-1.3.0"
    TESTDESC="Text-To-Speech Synthesis"
    TESTARGS=""

class TCPTS_x264_H264VideoEncoding(_PhoronixBase):
    TESTNAME="pts/x264-1.2.0"
    TESTDESC="H.264 Video Encoding"
    TESTARGS=""

class TCPTS_encodewavpack_WAVToWavPack(_PhoronixBase):
    TESTNAME="pts/encode-wavpack-1.2.0"
    TESTDESC="WAV To WavPack"
    TESTARGS=""

class TCPTS_nginx_StaticWebPageServing(_PhoronixBase):
    TESTNAME="pts/nginx-1.0.0"
    TESTDESC="Static Web Page Serving"
    TESTARGS=""

class TCPTS_tscp_AIChessPerformance(_PhoronixBase):
    TESTNAME="pts/tscp-1.0.0"
    TESTDESC="AI Chess Performance"
    TESTARGS=""

class TCPTS_gcrypt_CAMELLIA256ECBCipher(_PhoronixBase):
    TESTNAME="pts/gcrypt-1.0.0"
    TESTDESC="CAMELLIA256-ECB Cipher"
    TESTARGS=""

class TCPTS_povray_TotalTime(_PhoronixBase):
    TESTNAME="pts/povray-1.0.0"
    TESTDESC="Total Time"
    TESTARGS=""

class TCPTS_mrbayes_PrimatePhylogenyAnalysis(_PhoronixBase):
    TESTNAME="pts/mrbayes-1.2.0"
    TESTDESC="Primate Phylogeny Analysis"
    TESTARGS=""

class TCPTS_compress7zip_CompressSpeedTest(_PhoronixBase):
    TESTNAME="pts/compress-7zip-1.5.0"
    TESTDESC="Compress Speed Test"
    TESTARGS=""

class TCPTS_cachebench_WriteCache(_PhoronixBase):
    TESTNAME="pts/cachebench-1.0.0"
    TESTDESC="Write Cache"
    TESTARGS="-w"

class TCPTS_cachebench_ReadCache(_PhoronixBase):
    TESTNAME="pts/cachebench-1.0.0"
    TESTDESC="Read Cache"
    TESTARGS="-r"

class TCPTS_graphicsmagick_OperationHWBColorSpace(_PhoronixBase):
    TESTNAME="pts/graphics-magick-1.4.1"
    TESTDESC="Operation: HWB Color Space"
    TESTARGS="-colorspace HWB"

class TCPTS_johntheripper_TestMD5(_PhoronixBase):
    TESTNAME="pts/john-the-ripper-1.0.1"
    TESTDESC="Test: MD5"
    TESTARGS="MD5"

class TCPTS_johntheripper_Blowfish(_PhoronixBase):
    TESTNAME="pts/john-the-ripper-1.0.1"
    TESTDESC="Blowfish"
    TESTARGS="BLOWFISH"

class TCPTS_johntheripper_TestBlowfish(_PhoronixBase):
    TESTNAME="pts/john-the-ripper-1.0.1"
    TESTDESC="Test: Blowfish"
    TESTARGS="BLOWFISH"

class TCPTS_johntheripper_TestTraditionalDES(_PhoronixBase):
    TESTNAME="pts/john-the-ripper-1.0.1"
    TESTDESC="Test: Traditional DES"
    TESTARGS="TRADITIONAL_DES_MANY_SALTS"

class TCPTS_encodemp3_WAVToMP3(_PhoronixBase):
    TESTNAME="pts/encode-mp3-1.3.1"
    TESTDESC="WAV To MP3"
    TESTARGS=""

class TCPTS_compresspbzip2_256MBFileCompression(_PhoronixBase):
    TESTNAME="pts/compress-pbzip2-1.3.0"
    TESTDESC="256MB File Compression"
    TESTARGS=""

class TCPTS_encodeape_WAVToAPE(_PhoronixBase):
    TESTNAME="pts/encode-ape-1.3.0"
    TESTDESC="WAV To APE"
    TESTARGS=""

class TCPTS_bullet_TestConvexTrimesh(_PhoronixBase):
    TESTNAME="pts/bullet-1.0.0"
    TESTDESC="Test: Convex Trimesh"
    TESTARGS="convex-trimesh"

class TCPTS_bullet_Test3000Fall(_PhoronixBase):
    TESTNAME="pts/bullet-1.0.0"
    TESTDESC="Test: 3000 Fall"
    TESTARGS="3000 fall"

class TCPTS_hmmer_PfamDatabaseSearch(_PhoronixBase):
    TESTNAME="pts/hmmer-1.1.0"
    TESTDESC="Pfam Database Search"
    TESTARGS=""

class TCPTS_buildphp_TimeToCompile(_PhoronixBase):
    TESTNAME="pts/build-php-1.3.0"
    TESTDESC="Time To Compile"
    TESTARGS=""

class TCPTS_encodeflac_WAVToFLAC(_PhoronixBase):
    TESTNAME="pts/encode-flac-1.2.0"
    TESTDESC="WAV To FLAC"
    TESTARGS=""

class TCPTS_buildimagemagick_TimeToCompile(_PhoronixBase):
    TESTNAME="pts/build-imagemagick-1.5.1"
    TESTDESC="Time To Compile"
    TESTARGS=""

class TCPTS_ramspeed_IntegerAdd(_PhoronixBase):
    TESTNAME="pts/ramspeed-1.4.0"
    TESTDESC="Integer Add"
    TESTARGS="ADD -b 3"

class TCPTS_ramspeed_IntegerCopy(_PhoronixBase):
    TESTNAME="pts/ramspeed-1.4.0"
    TESTDESC="Integer Copy"
    TESTARGS="COPY -b 3"

class TCPTS_ramspeed_IntegerScale(_PhoronixBase):
    TESTNAME="pts/ramspeed-1.4.0"
    TESTDESC="Integer Scale"
    TESTARGS="SCALE -b 3"

class TCPTS_ramspeed_FloatingPointAdd(_PhoronixBase):
    TESTNAME="pts/ramspeed-1.4.0"
    TESTDESC="Floating-Point Add"
    TESTARGS="ADD -b 6"

class TCPTS_scimark2_Composite(_PhoronixBase):
    TESTNAME="pts/scimark2-1.1.1"
    TESTDESC="Composite"
    TESTARGS="TEST_COMPOSITE"

class TCPTS_fio_IntelIOMeterFileServerAccessPattern(_PhoronixBase):
    TESTNAME="pts/fio-1.1.0"
    TESTDESC="Intel IOMeter File Server Access Pattern"
    TESTARGS="examples/iometer-file-access-server"

class TCPTS_mafft_MultipleSequenceAlignment(_PhoronixBase):
    TESTNAME="pts/mafft-1.2.0"
    TESTDESC="Multiple Sequence Alignment"
    TESTARGS=""

class TCPTS_npb_TestClassMGB(_PhoronixBase):
    TESTNAME="pts/npb-1.0.0"
    TESTDESC="Test / Class: MG.B"
    TESTARGS="mg.B"

class TCPTS_npb_TestClassEPB(_PhoronixBase):
    TESTNAME="pts/npb-1.0.0"
    TESTDESC="Test / Class: EP.B"
    TESTARGS="ep.B"

class TCPTS_npb_TestClassLUA(_PhoronixBase):
    TESTNAME="pts/npb-1.0.0"
    TESTDESC="Test / Class: LU.A"
    TESTARGS="lu.A"

class TCPTS_npb_TestClassISC(_PhoronixBase):
    TESTNAME="pts/npb-1.0.0"
    TESTDESC="Test / Class: IS.C"
    TESTARGS="is.C"

class TCPTS_postmark_DiskTransactionPerformance(_PhoronixBase):
    TESTNAME="pts/postmark-1.0.0"
    TESTDESC="Disk Transaction Performance"
    TESTARGS=""

