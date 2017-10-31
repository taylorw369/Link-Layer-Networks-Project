'''
Created on Oct 12, 2016

@author: mwitt_000
'''
import queue
import math
import threading

class TableEntry:
    def __init__(self, to_addr, from_addr, outport):
        self.to_addr = to_addr
        self.from_addr = from_addr
        self.outport = outport

## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    def __init__(self, maxsize=0):
        self.queue = queue.Queue(maxsize);
        self.mtu = None
    
    ##get packet from the queue interface
    def get(self):
        try:
            return self.queue.get(False)
        except queue.Empty:
            return None
        
    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, block=False):
        self.queue.put(pkt, block)


## Implements a network layer packet (different from the RDT packet 
# from programming assignment 2).
# NOTE: This class will need to be extended to for the packet to include
# the fields necessary for the completion of this assignment.
class NetworkPacket:
    ## packet encoding lengths 
    dst_addr_S_length = 5
    header_length = dst_addr_S_length * 3 + 1
    pacs_sent = 0
    
    ##@param dst_addr: address of the destination host
    # @param data_S: packet payload
    def __init__(self, dst_addr, source_addr, data_S, segNum, moreflag=0):
        self.dst_addr = dst_addr
        self.source_addr = source_addr
        self.data_S = data_S
        self.size = len(data_S) + (self.dst_addr_S_length * 3) + 1
        self.segNum = segNum
        self.moreflag = moreflag

        
    ## called when printing the object
    def __str__(self):
        return self.to_byte_S() 

    def split(self, size):
        
        new_packets = []
        seg_num = self.segNum
        
        while len(self.data_S) > 0:
            if len(self.data_S) < size:
                p = NetworkPacket(self.dst_addr,self.source_addr, self.data_S, seg_num, self.moreflag)
                new_packets.append(p)
                self.data_S = ''
            else:
                temp1 = self.data_S[:size ]
                p = NetworkPacket(self.dst_addr, self.source_addr, temp1, seg_num, 1)
                new_packets.append(p)
                self.data_S = self.data_S[size:] #shorten data_S
        
        return new_packets
    
    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst_addr).zfill(self.dst_addr_S_length)
        byte_S += str(self.source_addr).zfill(self.dst_addr_S_length)
        byte_S += str(self.segNum).zfill(self.dst_addr_S_length)
        byte_S += str(self.moreflag)
        byte_S += self.data_S
        return byte_S
    
    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst_addr = int(byte_S[0 : NetworkPacket.dst_addr_S_length])
        source_addr = int(byte_S[ NetworkPacket.dst_addr_S_length:(NetworkPacket.dst_addr_S_length*2)])
        segNum = int(byte_S[NetworkPacket.dst_addr_S_length*2:(NetworkPacket.dst_addr_S_length*3)])
        moreflag = int(byte_S[(NetworkPacket.dst_addr_S_length * 3):((NetworkPacket.dst_addr_S_length*3)+1)])
        data_S = byte_S[((NetworkPacket.dst_addr_S_length*3)+1): ]
        # print("Destination: %s " % dst_addr)
        # print("Seg num: %s" % segNum)
        # print("moreflag: %s" % moreflag)
        return self(dst_addr, source_addr, data_S, segNum, moreflag)
    

    

## Implements a network host for receiving and transmitting data
class Host:
    idNum = 0
    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.in_intf_L = [Interface()]
        self.out_intf_L = [Interface()]
        self.stop = False #for thread termination
    
    ## called when printing the object
    def __str__(self):
        return 'Host_%s' % (self.addr)
       
    ## create a packet and enqueue for transmission
    # @param dst_addr: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst_addr, data_S):
        p = NetworkPacket(dst_addr,self.addr, data_S, Host.idNum)
        Host.idNum = Host.idNum + 1
        new_packets = p.split(self.out_intf_L[0].mtu - NetworkPacket.header_length)
        for pac in new_packets:
            self.out_intf_L[0].put(pac.to_byte_S()) #send packets always enqueued successfully
            print('%s: sending packet "%s" out interface with mtu=%d' % (self, pac, self.out_intf_L[0].mtu))

        
            
    # def udt_receive(self):
    #     pkt_S = self.in_intf_L[0].get()
    #     if pkt_S is not None:
    #         print('%s: received packet "%s"' % (self, pkt_S))

            
    ## receive packet from the network layer
    def udt_receive(self):
        #while loop until whole message is received
        pkt_S = self.in_intf_L[0].get()
        received_pacs = ''
        if pkt_S is not None:
            pac = NetworkPacket.from_byte_S(pkt_S)
            while pac.moreflag == 1:
                if pkt_S is not None:
                    pac = NetworkPacket.from_byte_S(pkt_S)
                    received_pacs = received_pacs + pac.data_S
                pkt_S = self.in_intf_L[0].get()

            # packets are already joined, print the whole one out
            print("\n")
            print('%s: recieved whole packet "%s"' % (self, received_pacs))
            print("\n")

            
    ## thread target for the host to keep receiving data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #receive data arriving to the in interface
            self.udt_receive()
            #terminate
            if(self.stop):
                print (threading.currentThread().getName() + ': Ending')
                return
        


## Implements a multi-interface router described in class
class Router:
    
    ##@param name: friendly router name for debugging
    # @param intf_count: the number of input and output interfaces 
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_count, max_queue_size, r_table):
        self.r_table = r_table
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        self.in_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]
        self.out_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]

    ## called when printing the object
    def __str__(self):
        return 'Router_%s' % (self.name)


    def determine_interface(self, packet):
        for entry in self.r_table:
            if entry.to_addr == packet.dst_addr and packet.source_addr == entry.from_addr:
                return entry.outport
        raise "Table entry not pressent. Stuff should explode..."
    
    ## look through the content of incoming interfaces and forward to
    # appropriate outgoing interfaces
    def forward(self):
        for i in range(len(self.in_intf_L)):
            pkt_S = None
            try:
                #get packet from interface i
                pkt_S = self.in_intf_L[i].get()
                #if packet exists make a forwarding decision
                if pkt_S is not None:
                    p = NetworkPacket.from_byte_S(pkt_S) #parse a packet out
                    # HERE you will need to implement a lookup into the 
                    # forwarding table to find the appropriate outgoing interface
                    # for now we assume the outgoing interface is also i
                    # split packets
                    out_inter = self.determine_interface(p)
                    new_packets = p.split(self.out_intf_L[out_inter].mtu - NetworkPacket.header_length)
                    for pac in new_packets:
                        self.out_intf_L[out_inter].put(pac.to_byte_S()) #send packets always enqueued successfully
                        print('%s: sending packet "%s" out interface with mtu=%d' % (self, pac, self.out_intf_L[out_inter].mtu))
            except queue.Full:
                print('%s: packet "%s" lost on interface %d' % (self, p, i))
                pass
            
                
    ## thread target for the host to keep forwarding data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            self.forward()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return 
