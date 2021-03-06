#
# XenRT: Test harness for Xen and the XenServer product family
#
# Encapsulate a libvirt pool.
#
# Copyright (c) 2006 XenSource, Inc. All use and distribution of this
# copyrighted material is governed by and subject to terms and
# conditions as licensed by XenSource, Inc. All other rights reserved.
#

import xenrt

class KVMPool(xenrt.lib.libvirt.Pool):

    """A "pool" of KVM hosts."""
    def __init__(self, master):
        xenrt.lib.libvirt.Pool.__init__(self, master)

    def hostFactory(self):
        return xenrt.lib.libvirt.KVMHost
