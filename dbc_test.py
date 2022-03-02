#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys, getopt
import re
import os
from collections import OrderedDict
def main(argv):
    dbcfile = '243.dbc'  # Default value unless overriden
    self_node = 'DRIVER'  # Default value unless overriden
    gen_all = False
    muxed_signal = False
    mux_bit_width = 0
    msg_ids_used = []
    try:
        opts, args = getopt.getopt(argv, "i:s:a", ["ifile=", "self=", "all"])
    except getopt.GetoptError:
        print('dbc_parse.py -i <dbcfile> -s <self_node> <-a>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('dbc_parse.py -i <dbcfile> -s <self_node> <-a> <-b>')
            sys.exit()
        elif opt in ("-i", "--ifile"):
            dbcfile = arg
        elif opt in ("-s", "--self"):
            self_node = arg
        elif opt in ("-a", "--all"):
            gen_all = True
 
    # Parse the DBC file
    dbc = DBC(dbcfile, self_node, gen_all)
    f = open(dbcfile, "r")
    last_mid = -1
    validFile = True
    while 1:
        line = f.readline()
        if not line:
            break
 
        # Nodes in the DBC file
        if line.startswith("BU_:"):
            nodes = line.strip("\n").split(' ')
            dbc.nodes = (nodes[1:])
            if self_node not in dbc.nodes:
                print('/// ERROR /')
                print('#error "Self node: ' + self_node + ' not found in _BU nodes in the DBC file"')
                print('/// ERROR /')
                print('')
                raise ValueError('#error "Self node: ' + self_node + ' not found in _BU nodes in the DBC file"')
 
        # Start of a message
        # BO_ 100 DRIVER_HEARTBEAT: 1 DRIVER
        if line.startswith("BO_ "):
            muxed_signal = False
            mux_bit_width = 0
            tokens = line.split(' ')
            msg_id = hex(int(tokens[1],10))
            msg_name = tokens[2].strip(":")
            dbc.messages[msg_id] = Message(msg_id, msg_name, tokens[3], tokens[4].strip("\n"))
            msg_length = tokens[3]
            last_mid = msg_id
            fixed_mux_signal = False
            fixed_signal_end = 0
            prev_signal_end = 0
            prev_mux_index = 0
 
            if (int(msg_id, 16) < 0) or (int(msg_id, 16) > 536870911):
                print('/// ERROR /')
                print('#error msg id '+ tokens[1] + ' is out of bounds')
                print('/// ERROR /')
                print('')
                raise ValueError('#error msg id '+ tokens[1] + ' is out of bounds for 29-bit msgID')
 
            if msg_id not in msg_ids_used:
                msg_id = msg_ids_used.append(msg_id)
            else:
                print('/// ERROR /')
                print('#error '+ tokens[1] + ' has already been used')
                print('/// ERROR /')
                print('')
                raise ValueError('#error msg id '+ msg_id + ' has already been used')
 
            if (int(msg_length) > 8) or (int(msg_length) < 0):
                print('/// ERROR /')
                print('#error ' + str(tokens[1]) + ' has an incorrect number of bytes. It must be between 0 and 8 bytes.')
                print('/// ERROR /')
                print('')
                raise ValueError('#error msg id ' + str(tokens[1]) + ' has an incorrect number of bytes. It must be between 0 and 8 bytes.')
 
        # Signals: SG_ IO_DEBUG_test_signed : 16|8@1+ (1,-128) [0|0] "" DBG
        if line.startswith(" SG_ "):
            t = line[1:].split(' ')
 
            # If this is a MUX'd symbol
            mux = ''
            if t[3] == ":":
                mux = t[2]
                line = line.replace(mux + " ", '')
                t = line[1:].split(' ')
 
            # Split the bit start and the bit size
            s = re.split('[|@]', t[3])
            bit_start = s[0]
            bit_size = s[1]
 
            if mux == 'M':
                muxed_signal = True
                mux_bit_width = int(bit_size)
 
            if not muxed_signal:
                if (int(bit_start) < prev_signal_end):
                    print('/// ERROR /')
                    print('#error ' + t[1] + ' start bit overwrites previous signal')
                    print('/// ERROR /')
                    print('')
                    raise ValueError('#error ' + t[1] + ' start bit overwrites previous signal')
                prev_signal_end = int(bit_start) + int(bit_size)
            # Ensure a mux index
            if muxed_signal:
                if mux == '':
                    fixed_mux_signal = True
                    fixed_signal_end = mux_bit_width + int(bit_size)
                elif mux[0] == 'm':
                    fixed_mux_signal = False
                    if int(mux[1:]) != prev_mux_index:
                        prev_signal_end = fixed_signal_end
 
                if fixed_mux_signal:
                    if int(bit_start) < mux_bit_width:
                        print('/// ERROR /')
                        print('#error ' + t[1] + ' start bit overwrites mux index')
                        print('/// ERROR /')
                        print('')
                        raise ValueError('#error ' + t[1] + ' start bit overwrites mux index')
                else:
                    if mux != 'M':
                        # Do not allow the signal to use the indexing bits
                        if int(bit_start) < fixed_signal_end:
                            print('/// ERROR /')
                            print('#error ' + t[1] + ' start bit overwrites mux index')
                            print('/// ERROR /')
                            print('')
                            raise ValueError('#error ' + t[1] + ' start bit overwrites previous fixed signal')
                        if mux[0] == 'm':
                        # Check for mux index out of bounds
                            if (int(mux[1:]) >= pow(2,mux_bit_width)) or (int(mux[1:]) < 0):
                                print('/// ERROR /')
                                print('#error ' + t[1] + ' mux index out of bounds.')
                                print('/// ERROR /')
                                print('')
                                raise ValueError('#error ' + t[1] + ' mux index out of bounds.')
 
                            if int(bit_start) < prev_signal_end:
                                print('/// ERROR /')
                                print('#error ' + t[1] + ' start bit overwrites previous signal')
                                print('/// ERROR /')
                                print('')
                                raise ValueError('#error ' + t[1] + ' start bit overwrites previous signal')
                            prev_signal_end = int(bit_start) + int(bit_size)
                        prev_mux_index = int(mux[1:])
 
            # If we have an invalid message length then invalidate the DBC and print the offending signal
            # Signal bit width is <= 0
            if (int(bit_size) <= 0):
                print('/// ERROR /')
                print('#error ' + t[1] + ' has invalid size. Signal bit width is: ' + str(int(bit_size)))
                print('/// ERROR /')
                print('')
                raise ValueError('#error ' + t[1] + ' has invalid size. Signal bit width is: ' + str(int(bit_size)))
 
            # Signal is too wide for message
            if (int(bit_start) + int(bit_size)) > (int(msg_length) * 8):
                print('/// ERROR /')
                print('#error ' + t[1] + ' too large. Message needs ' + str(int(bit_start) + int(bit_size)) + ' bits.')
                print('/// ERROR /')
                print('')
                raise ValueError('#error ' + t[1] + ' too large. Message needs ' + str(int(bit_start) + int(bit_size)) + ' bits.')
 
            endian_and_sign = s[2]
            # Split (0.1,1) to two tokens by removing the ( and the )
            s = t[4][1:-1].split(',')
            scale = s[0]
            offset = s[1]
 
            # Split the [0|0] to min and max
            s = t[5][1:-1].split('|')
            min_val = s[0]
            max_val = s[1]
 
            signal_min = 0
            signal_max = (float(scale) * pow(2,int(bit_size)))
            if '-' in t[3]:
                signal_min = -(float(scale) * pow(2,int(bit_size))) / 2
                signal_max = (float(scale) * pow(2,int(bit_size)) / 2)
            # If our min / max values are incorrect then clamping will not work correctly.
            # Invalidate the DBC and print out the offending signal.
            signal_min = signal_min + float(offset)
            signal_max = signal_max + float(offset) - float(scale)
 
            # Min for signal is too low.
            if (float(min_val) != 0) and (float(min_val) < float(signal_min)):
                print('/// ERROR /')
                print('#error ' + t[1] + ' min value too low. Min value is: ' + str(signal_min))
                print('/// ERROR /')
                print('')
                raise ValueError('#error ' + t[1] + ' min value too low. Min value is: ' + str(signal_min))
 
            # Max for signal is too high
            if (float(max_val) != 0) and (float(max_val)) > (float(signal_max)):
                print('/// ERROR /')
                print('#error ' + t[1] + ' max value too high. Max value is: ' + str(signal_max))
                print('/// ERROR /')
                print('')
                raise ValueError('#error ' + t[1] + ' max value too high. Max value is: ' + str(signal_max))
 
            recipients = t[7].strip('\n').split(',')
 
            # Add the signal the last message object
            sig = Signal(t[1], bit_start, bit_size, endian_and_sign, scale, offset, min_val, max_val, recipients, mux, signal_min, signal_max)
            dbc.messages[last_mid].add_signal(sig)
 
        # Parse the "FieldType" which is the trigger to use enumeration type for certain signals
        if line.startswith('BA_ "FieldType"'):
            t = line[1:].split(' ')  # BA_ "FieldType" SG_ 123 Some_sig "Some_sig";
            sig_mid = t[3]
            sig_name = t[4]
 
            # Locate the message and the signal whom this "FieldType" type belongs to
            if sig_mid in dbc.messages:
                if sig_name in dbc.messages[sig_mid].signals:
                    dbc.messages[sig_mid].signals[sig_name].has_field_type = True
 
        # Enumeration types
        # VAL_ 100 DRIVER_HEARTBEAT_cmd 2 "DRIVER_HEARTBEAT_cmd_REBOOT" 1 "DRIVER_HEARTBEAT_cmd_SYNC" ;
        if line.startswith("VAL_ "):
            t = line[1:].split(' ')
            sig_mid = t[1]
            enum_name = t[2]
            pairs = {}
            t = t[3:]
            for i in range(0, int(len(t) / 2)):
                pairs[t[i * 2 + 1].replace('"', '').replace(';\n', '')] = t[i * 2]
 
            # Locate the message and the signal whom this enumeration type belongs to
            if sig_mid in dbc.messages:
                if enum_name in dbc.messages[sig_mid].signals:
                    if dbc.messages[sig_mid].signals[enum_name].has_field_type:
                        dbc.messages[sig_mid].signals[enum_name].enum_info = pairs
 
    # If there were errors in parsing the DBC file then do not continue with generation.
    if not validFile:
        sys.exit(-1)
    
    print(HeadCode)
    print(dbc.gen_file_header())
    print("\n")
 
    # Generate the application send extern function
    print("/// Extern function needed for dbc_encode_and_send()")
    print("extern bool dbc_app_send_can_msg(uint32_t mid, uint8_t dlc, uint8_t bytes[8]);")
    print("")
 
    # Generate header structs and MIA struct
    print(dbc.gen_mia_struct())
    print(dbc.gen_msg_hdr_struct())
    print(dbc.gen_msg_hdr_instances())
    print(dbc.gen_enum_types())
 
    # Generate converted struct types for each message
    for mid in dbc.messages:
        m = dbc.messages[mid]
        if not gen_all and not m.is_recipient_of_at_least_one_sig(self_node) and m.sender != self_node:
            code = ("\n// Not generating '" + m.get_struct_name() + "' since we are not the sender or a recipient of any of its signals")
        else:
            print(m.gen_converted_struct(self_node, gen_all))
 
    # Generate MIA handler "externs"
    print("\n/// @{ These 'externs' need to be defined in a source file of your project")
    for mid in dbc.messages:
        m = dbc.messages[mid]
        if gen_all or m.is_recipient_of_at_least_one_sig(self_node):
            if m.contains_muxed_signals():
                muxes = m.get_muxes()
                for mux in muxes[1:]:
                    print(str("extern const uint32_t ").ljust(50) + (m.name + "_" + mux + "__MIA_MS;"))
                    print(str("extern const " + m.get_struct_name()[:-2] + "_" + mux + "_t").ljust(49) + " " + (
                    m.name + "_" + mux + "__MIA_MSG;"))
            else:
                print(str("extern const uint32_t ").ljust(50) + (m.name + "__MIA_MS;"))
                print(str("extern const " + m.get_struct_name()).ljust(49) + " " + (m.name + "__MIA_MSG;"))
    print("/// @}\n")
 
    # Generate encode methods
    for mid in dbc.messages:
        m = dbc.messages[mid]
        if not gen_all and m.sender != self_node:
            print ("\n/// Not generating code for dbc_encode_" + m.get_struct_name()[:-2] + "() since the sender is " + m.sender + " and we are " + self_node)
        else:
            print(m.get_encode_code())
 
    # Generate decode methods
    for mid in dbc.messages:
        m = dbc.messages[mid]
        if not gen_all and not m.is_recipient_of_at_least_one_sig(self_node):
            print ("\n/// Not generating code for dbc_decode_" + m.get_struct_name()[:-2] + "() since '" + self_node + "' is not the recipient of any of the signals")
        else:
            print(m.get_decode_code())
 
    print(dbc.gen_mia_funcs())
    print("#endif")
 
 
if __name__ == "__main__":
    main(sys.argv[1:])