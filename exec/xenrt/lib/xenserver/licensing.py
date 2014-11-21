import xenrt
from xenrt.enum import XenServerLicenceSKU
from abc import ABCMeta, abstractmethod

__all__ = ["CreedenceLicence", "TampaLicence", "ClearwaterLicence", "XenServerLicenceFactory", "LicenceManager"]


class LicenceManager(object):
    def addLicensesToServer(self, v6, license):
        v6.addLicense(license.getLicenceFileName())
        totalLicenses, licenseinUse = v6.getLicenseInUse(license.getLicenceName())
        return licenseinUse

    def applyLicense(self, v6, hostOrPool, license):
        self.addLicensesToServer(v6, license)
        hostOrPool.licenseApply(v6,license)
        self.verifyLicenseServer(license.getEdition()) # TO GO?

    def releaseLicense(self, hostOrPool):
        hostOrPool.license(v6server=None, sku='free', usev6testd=False)

    def verifyLicenseServer(self, license, v6, licenseinUse, hostOrPool, reset=False):

        xsOnlyLicences = XenServerLicenceFactory().xenserverOnlyLicences()
        if not next((i for i in xsOnlyLicences if i.getEdition() == license.getEdition()), None):
            xenrt.TEC().logverbose("XD license is applied so no need to verify the license server")
            return

        tmp,currentLicinuse = v6.getLicenseInUse(license.getLicenceName())

        if reset:
            if licenseinUse != currentLicinuse:
                raise xenrt.XRTFailure("Not all the licenses are not returned to license server, current licenses in use %d" % (currentLicinuse))
            xenrt.TEC().logverbose("License server verified and correct no of licenses checked out")
            return

        if not ((hostOrPool.getNoOfSockets() + licenseinUse)  == currentLicinuse):
            raise xenrt.XRTFailure("No. of Licenses in use: %d, No. of socket in whole pool: %d" % (currentLicinuse, hostOrPool.getNoOfSockets()))

        xenrt.TEC().logverbose("License server verified and correct no of licenses checked out")


class Licence(object):
    __metaclass__ = ABCMeta

    def __init__(self, sku):
        self.sku = sku

    @abstractmethod
    def getEdition(self):
        """
        Edition used by xapi for the given sku
        @rtype string
        """
        pass

    @abstractmethod
    def getLicenceFileName(self):
        """
        File name for the given SKU
        @rtype string
        """
        pass

    @abstractmethod
    def getLicenceName(self):
        """
        License servers understanding of a given SKU
        @rtype string
        """
        pass

    def verify(self):
        self.getEdition()
        self.getLicenceFileName()
        self.getLicenceName()

    def __str__(self):
        return "SKU: %s; Edition: %s; FileName: %s; LicenceServerName: %s" % (self.sku,
                                                                              self.getEdition(),
                                                                              self.getLicenceFileName(),
                                                                              self.getLicenceName())


class TampaLicence(Licence):
    """
    PLACEHOLDER CLASS
    """
    def getEdition(self):
        return "licence"

    def getLicenceFileName(self):
        return "licence.lic"

    def getLicenceName(self):
        return "CXS_some_thing"


class ClearwaterLicence(Licence):
    """
    PLACEHOLDER CLASS
    """
    def getEdition(self):
        return "licence"

    def getLicenceFileName(self):
        return "licence.lic"

    def getLicenceName(self):
        return "CXS_some_thing"


class CreedenceLicence(Licence):

    def getEdition(self):
        if self.sku == XenServerLicenceSKU.PerUserEnterprise or \
           self.sku == XenServerLicenceSKU.PerConcurrentUserEnterprise:
            return "enterprise-per-user"
        if self.sku == XenServerLicenceSKU.PerSocketEnterprise or \
           self.sku == XenServerLicenceSKU.PerSocket:
            return "enterprise-per-socket"
        if self.sku == XenServerLicenceSKU.XenDesktopPlatinum:
            return "xendesktop"
        if self.sku == XenServerLicenceSKU.PerSocketStandard:
            return "standard-per-socket"
        if self.sku == XenServerLicenceSKU.Free:
            return "free"
        raise ValueError("No edition found for the SKU %s" % self.sku)

    def getLicenceFileName(self):
        if self.sku == XenServerLicenceSKU.PerSocketEnterprise:
            return "valid-enterprise-persocket"
        if self.sku == XenServerLicenceSKU.PerUserEnterprise:
            return "valid-enterprise-peruser"
        if self.sku == XenServerLicenceSKU.PerConcurrentUserEnterprise:
            return "valid-enterprise-perccu"
        if self.sku == XenServerLicenceSKU.XenDesktopPlatinum:
            return "valid-xendesktop"
        if self.sku == XenServerLicenceSKU.PerSocketStandard:
            return "valid-standard-persocket"
        if self.sku == XenServerLicenceSKU.Free:
            return None
        if self.sku == XenServerLicenceSKU.PerSocket:
            return "valid-persocket"
        raise ValueError("No license file name found for the SKU %s" % self.sku)

    def getLicenceName(self):
        if self.sku == XenServerLicenceSKU.PerSocketEnterprise:
            return "CXS_ENT2_CCS"
        if self.sku == XenServerLicenceSKU.PerUserEnterprise:
            return "CXS_ENT2_UD"
        if self.sku == XenServerLicenceSKU.PerConcurrentUserEnterprise:
            return "CXS_ENT2_CCU"
        if self.sku == XenServerLicenceSKU.XenDesktopPlatinum:
            return "XDS_STD_CCS"
        if self.sku == XenServerLicenceSKU.PerSocketStandard:
            return "CXS_STD2_CCS"
        if self.sku == XenServerLicenceSKU.Free:
            return None
        if self.sku == XenServerLicenceSKU.PerSocket:
            return "CXS_STD_CCS"
        raise ValueError("No license server name found for the SKU %s" % self.sku)


class XenServerLicenceFactory(object):
    __TAM = "tampa"
    __CLR = "clearwater"
    __CRE = "creedence"

    def __getHostAge(self, xshost):
        return xshost.productVersion.lower()

    def xenserverOnlyLicencesForPool(self, xspool):
        return self.xenserverOnlyLicences(xspool.master)

    def xenserverOnlyLicencesForHost(self, xshost):
        lver = self.__getHostAge(xshost)
        return self.xenserverOnlyLicences(lver)

    def xenserverOnlyLicences(self, productVersion):
        lver = productVersion.lower()
        if lver == self.__CRE:
            skus = [XenServerLicenceSKU.PerSocketEnterprise,
                    XenServerLicenceSKU.PerSocketStandard,
                    XenServerLicenceSKU.PerSocket]
            return [self.licence(lver, s) for s in skus]

        raise ValueError("No licence object was found for the provided host version: %s" % productVersion)

    def allLicencesForPool(self, xspool):
        return self.allLicences(xspool.master)

    def allLicencesForHost(self, xshost):
        lver = self.__getHostAge(xshost)
        return self.allLicences(lver)

    def allLicences(self, productVersion):
        lver = productVersion.lower()
        if lver == self.__CRE:
            skus = [XenServerLicenceSKU.PerSocketEnterprise, XenServerLicenceSKU.PerUserEnterprise,
                    XenServerLicenceSKU.PerConcurrentUserEnterprise, XenServerLicenceSKU.XenDesktopPlatinum,
                    XenServerLicenceSKU.PerSocketStandard, XenServerLicenceSKU.Free, XenServerLicenceSKU.PerSocket]
            return [self.licence(lver, s) for s in skus]

        raise ValueError("No licence object was found for the provided host version: %s" % productVersion)

    def licenceForPool(self, xspool, sku):
        return self.licence(xspool.master, sku)

    def licenceForHost(self, xshost, sku):
        lver = self.__getHostAge(xshost)
        return self.licence(lver, sku)

    def licence(self, productVersion, sku):
        lver = productVersion.lower()
        if lver == self.__TAM:
            return TampaLicence(sku)
        if lver == self.__CLR:
            return ClearwaterLicence(sku)
        if lver == self.__CRE:
            return CreedenceLicence(sku)
        raise ValueError("No licence object was found for the provided host version: %s" % productVersion)
