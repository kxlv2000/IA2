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
        self.linkInfo = dict()

    def add_info(self, h1, h2, bw):
        if h1 not in self.linkInfo:
            self.linkInfo[h1] = dict()
        self.linkInfo[h1][h2] = int(bw)

    def read(self, filename):
        f = open(filename)
        head = f.readline().strip().split(' ')
        lines = f.readlines()
        f.close()
        N, M, L = [int(i) for i in head]

        for n in range(N):
            self.addHost('h%d' % (n+1))

        for m in range(M):
            t_head = {'dpid': "%016x" % (m+1)}
            self.addSwitch('s%d' % (m+1), **t_head)

        for l in lines:
            d1, d2, bw = l.strip().split(',')
            self.add_info(d1, d2, bw)
            self.add_info(d2, d1, bw)
            self.addLink(d1, d2)


def startNetwork():
    info('** Creating the tree network\n')
    topo = TreeTopo()
    topo.read("topology.in")

    global net
    net = Mininet(topo=topo, link=TCLink,
                  controller=lambda name: RemoteController(
                      name, ip='192.168.56.1'),
                  listenPort=6633, autoSetMacs=True)

    info('** Starting the network\n')
    net.start()

    # Create QoS Queues
    for switch in net.switches:
        for intf in switch.intfList():
            if intf.link:
                if intf.link.intf1.node == switch:
                    targets = intf.link.intf2.node
                    sw_intf = intf.link.intf1
                else:
                    targets = intf.link.intf1.node
                    sw_intf = intf.link.intf2
                bw = topo.linkInfo[switch.name][targets.name]*1000000
                os.system('sudo ovs-vsctl -- set Port %s qos=@newqos \
               -- --id=@newqos create QoS type=linux-htb other-config:max-rate=%d queues=0=@q0,1=@q1\
               -- --id=@q0 create queue other-config:max-rate=%d \
               -- --id=@q1 create queue other-config:min-rate=%d'
                          % (sw_intf, bw, bw*0.5, bw*0.8))

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
