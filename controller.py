'''
Please add your name:Qing Bowen
Please add your matric number: A0243489R
'''

import sys
import os
from sets import Set

from pox.core import core

import pox.openflow.libopenflow_01 as of
import pox.openflow.discovery
import pox.openflow.spanning_tree

from pox.lib.revent import *
from pox.lib.util import dpid_to_str
from pox.lib.addresses import IPAddr, EthAddr

import time

log = core.getLogger()

class Controller(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)

        self.ttl_table, self.flow_table = dict(), dict()
        self.premium, self.policies = list(), list()

    def _handle_PacketIn(self, event):
        packet, dpid = event.parsed, event.dpid
        src, dst = packet.src, packet.dst
        if packet.type == packet.IP_TYPE:
            srcIP, dstIP = packet.payload.srcip, packet.payload.dstip
        else:
            srcIP, dstIP = packet.payload.protosrc, packet.payload.protodst
            if dst.is_multicast:
                dst = EthAddr("%012x" %
                              (int(str(dstIP).split('.')[-1]) & 0xffFFffFFffFF))

        # install entries to the route table
        def install_enqueue(event, packet, outport, q_id):
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, event.port)
            msg.data = event.ofp
            msg.idle_timeout, msg.hard_timeout = 10, 10
            msg.priority = 1
            msg.actions.append(of.ofp_action_enqueue(
                port=outport, queue_id=q_id))
            event.connection.send(msg)

        # Check the packet and decide how to route the packet
        def forward(message=None):
            if (dst not in self.flow_table[dpid]) or dst.is_multicast:
                flood()
            else:
                install_enqueue(event, packet, self.flow_table[dpid][dst], int(
                    (str(srcIP) in self.premium) or (str(dstIP) in self.premium)))

        # When it knows nothing about the destination, flood but don't install the rule
        def flood(message=None):
            msg = of.ofp_packet_out()
            msg.in_port = event.port
            msg.data = event.ofp
            msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
            event.connection.send(msg)

        if dpid not in self.flow_table:
            self.ttl_table[dpid], self.flow_table[dpid] = dict(), dict()

        if src not in self.flow_table[dpid]:
            self.ttl_table[dpid][src] = time.time()
            self.flow_table[dpid][src] = event.port

        forward()

        if dst in self.ttl_table[dpid] and time.time() > self.ttl_table[dpid][dst] + 10:
            self.ttl_table[dpid].pop(dst)
            self.flow_table[dpid].pop(dst)

    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        log.debug("Switch %s has come up.", dpid)

        fd = open("pox/misc/policy1.in")
        config = fd.readline().strip().split(' ')
        N, M = int(config[0]), int(config[1])

        for x in range(N):
            line = [x.strip() for x in fd.readline().split(",")]
            if len(line) == 3:
                self.policies.append(line)
            else:
                self.policies.append((None, line[0], line[1]))

        for x in range(M):
            self.premium.append(fd.readline().strip())

        for policy in self.policies:
            block = of.ofp_match()
            block.nw_proto = 6
            block.dl_type = 0x0800
            if policy[0]:
                block.nw_src = IPAddr(policy[0])
            if policy[1]:
                block.nw_dst = IPAddr(policy[1])
                block.tp_dst = int(policy[2])
            msg = of.ofp_flow_mod()
            msg.match = block
            msg.priority = 2
            event.connection.send(msg)

def launch():
    # Run discovery and spanning tree modules
    pox.openflow.discovery.launch()
    pox.openflow.spanning_tree.launch()
    # Starting the controller module
    core.registerNew(Controller)