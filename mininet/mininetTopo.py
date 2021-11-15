'''
Please add your name: Qing Bowen
Please add your matric number: A0243489R
'''

import os
import sys
import atexit
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.node import RemoteController

net = None

class TreeTopo(Topo):
            
    def __init__(self):
        # Initialize topology
        Topo.__init__(self)
        self.linkInfo = {}

    def addLinkInfo(self, h1, h2, bw):
        if h1 not in self.linkInfo:
            self.linkInfo[h1] = {}
        self.linkInfo[h1][h2] = int(bw)

    def readFromFile(self, filename):
        f = open(filename)
        config = f.readline().strip().split(' ')
        lines = f.readlines()
        f.close()
        N, M, L = [int(i) for i in config]

        for n in range(N):
            self.addHost('h%d' % (n+1))
            
        for m in range(M):
            sconfig = {'dpid': "%016x" % (m+1)}
            self.addSwitch('s%d' % (m+1), **sconfig)

        for l in lines:
            d1, d2, bw = l.strip().split(',')
            self.addLinkInfo(d1,d2,bw)
            self.addLinkInfo(d2,d1,bw)
            self.addLink(d1, d2)

def createQosQueue(net, target, switch_interface, bw):
    os.system('sudo ovs-vsctl -- set Port %s qos=@newqos \
               -- --id=@newqos create QoS type=linux-htb other-config:max-rate=%d queues=0=@q0,1=@q1,2=@q2 \
               -- --id=@q0 create queue other-config:max-rate=%d \
               -- --id=@q1 create queue other-config:min-rate=%d'
               % (switch_interface, bw*1000000, bw*0.5*1000000, bw*0.8*1000000))

def createQosQueues(net, linkInfo):
    for switch in net.switches:
        for intf in switch.intfList():
            if intf.link:
                n1 = intf.link.intf1.node
                n2 = intf.link.intf2.node
                target = n2 if n1 == switch else n1
                switch_interface = intf.link.intf1 if n1 == switch else intf.link.intf2
                bw = linkInfo[switch.name][target.name]
                switch_interface_name = switch_interface.name
                createQosQueue(net, target, switch_interface_name, bw)


def startNetwork():
    info('** Creating the tree network\n')
    topo = TreeTopo()
    topo.readFromFile("topology.in")

    global net
    net = Mininet(topo=topo, link = TCLink,
                  controller=lambda name: RemoteController(name, ip='192.168.56.1'),
                  listenPort=6633, autoSetMacs=True)

    info('** Starting the network\n')
    net.start()
    net.waitConnected()

    info('** Creating QoS Queues\n')
    createQosQueues(net, topo.linkInfo)

    # Create QoS Queues
    
    info('** Running CLI\n')
    CLI(net)

def stopNetwork():
    if net is not None:
        net.stop()
        # Remove QoS and Queues
        os.system('sudo ovs-vsctl --all destroy Qos')
        os.system('sudo ovs-vsctl --all destroy Queue')


if __name__ == '__main__':
    # Force cleanup on exit by registering a cleanup function
    atexit.register(stopNetwork)

    # Tell mininet to print useful information
    setLogLevel('info')
    startNetwork()
