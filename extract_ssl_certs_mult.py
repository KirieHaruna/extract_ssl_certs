#coding=gbk
#version:20161109
import dpkt
import struct, socket, sys, os, argparse, md5

import multiprocessing

def showUsage():
    print 'extract_ssl_certs.py [-f �ļ���|-d Ŀ¼]'

def extract_file(filepath):
    if not filepath.endswith('cap'):
        return

    print 'Extract: %s' % (filepath)
    tcp_piece={}
    f = open(filepath,'rb')
    try:
        pcap = dpkt.pcap.Reader(f)
    except:
        print "Error reading cap: %s", filepath
        return

    count=0
    try:
        for ts, buf in pcap:
            count+=1
            try:
                upperdata=dpkt.ethernet.Ethernet(buf).data
                while upperdata.__class__ not in [dpkt.ip.IP, str]:   #ѭ��ȥ��IP�㣬����Ҫ�ǽ��һЩ������pppoe��ppp���Ե��
                    upperdata=upperdata.data
                if upperdata.__class__==dpkt.ip.IP:
                    #if upperdata.sport!=443: continue
                    ippack=upperdata
                    tcppack=ippack.data
                    ssldata=tcppack.data
                else:   #IP��δ�ҵ�
                    continue
                if not ssldata: continue    #����ǿվ��ӵ��ˣ������Ǹ�ͬһ��SEQ��Ӧ��ACK�İ�
                srcip=socket.inet_ntoa(ippack.src)
                #������һ����Ԫ�飨ԴIP��Ŀ��IP��Դ�˿ڣ�Ŀ�Ķ˿ڣ�
                tuple4=(srcip, socket.inet_ntoa(ippack.dst), tcppack.sport, tcppack.dport)
                seq=tcppack.seq
                if not tcp_piece.has_key(tuple4):
                    tcp_piece[tuple4]={}
                tcp_piece[tuple4][seq]=ssldata
            except Exception,e:
                pass
    except Exception,e:
        print e.message
    f.close()
        
    #A->B��B->A�ǰ�������ͳ�Ƶģ����Ա���һ��Դ���Ϳ��Ա��������������
    for t4,dic in tcp_piece.iteritems():    #����4Ԫ���������
        srcip=t4[0]
        sport=t4[2]
        #md5_dstip_dstport=md5.md5(t4[1]+str(t4[3])).hexdigest()
        seq=min(dic.keys())
        sslcombined=dic[seq]
        piecelen=len(dic[seq])
        while(dic.has_key(seq+piecelen)):
            seq=seq+piecelen
            sslcombined+=dic[seq]
            piecelen=len(dic[seq])
        totallen=len(sslcombined)
        
        #do something
        curpos=0        
        while(curpos<totallen):
            #����ر�С��ֱ������
            if totallen-curpos<12: break
            #�������Handshake����
            if sslcombined[curpos]!='\x16':
                break
            handshake_len=struct.unpack('!H', sslcombined[curpos+3:curpos+5])[0]
            curpos+=5
            cur_handshakelen=0
            while(cur_handshakelen<handshake_len):
                this_handshake_len=struct.unpack('!I', '\x00'+sslcombined[curpos+1:curpos+4])[0]
                cur_handshakelen+=this_handshake_len+4
                if sslcombined[curpos]=='\x0b': #�����һ����֤��
                    certlen=struct.unpack('!I', '\x00'+sslcombined[curpos+4:curpos+7])[0]
                    if certlen>totallen:    #֤��ĳ��ȳ��������ݰ��ĳ��ȣ�ͨ�������ݰ����ݶ�ʧ���µ�
                        break                    
                    curpos+=7
                    sub_cert_len=0  #������֤����ܴ�С            
                    sub_cert_count=1    #��֤���ţ�����γ�֤������Խ����ԽС
                    while(sub_cert_len<certlen):
                        this_sub_len=struct.unpack('!I', '\x00'+sslcombined[curpos:curpos+3])[0]   #��ǰ��֤���С
                        curpos+=3
                        this_sub_cert=sslcombined[curpos:curpos+this_sub_len]
                        sub_cert_len+=this_sub_len+3    #+3�ǡ�֤�鳤�ȡ���3���ֽ�
                        curpos+=this_sub_len
                        md5cert=md5.md5(this_sub_cert).hexdigest()
                        filename='%s_%d_%d_%s.cer' % (srcip, sport, sub_cert_count, md5cert)
                        try:
                            os.mkdir('certs\\%s'%srcip)
                        except:
                            pass
                        with open('certs\\%s\\%s'%(srcip,filename), 'wb') as f:
                            f.write(this_sub_cert)
                        print filename
                        sub_cert_count+=1      
                else:
                    curpos+=this_handshake_len+4  #����֤��ֱ������
                
if __name__=="__main__":
    parser = argparse.ArgumentParser(description='Extract SSL certs')
    parser.add_argument("-f", "--file", action='store', help="Extract SSL certificates from a single file.", default = None)
    parser.add_argument("-d", "--dir", action='store', help="Extract SSL certificates from a directory containing cap files.", default = None)
    #parser.add_argument("-e", "--exclude", action='store', help="Filename containing skip ip list, ip list in this file will be skip when extracting.", default=None)
    #parser.add_argument("-h", "--help")
    args = parser.parse_args()
    
    if args.file is None and args.dir is None or args.file is not None and args.dir is not None:
        print "Either -f or -d is required, but can't be both there."
        showUsage()
        exit(-1)

    try:
        os.mkdir('certs')
    except:
        pass
    
    cpu_core=multiprocessing.cpu_count()-1
    if cpu_core<1:
        cpu_core=1
    pool=multiprocessing.Pool(cpu_core)
    
    if args.dir!=None:
        for root, parent, files in os.walk(args.dir):
            if files!=[]:
                pool.map(extract_file, map(lambda x:root+os.sep+x, files))
                
    elif args.file!=None:
        extract_file(args.file)
    
