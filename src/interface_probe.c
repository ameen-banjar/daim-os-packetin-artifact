#include <inttypes.h>
#include <stddef.h>
#include <stdio.h>

#include "daim_os_api.h"
#include "daim_os_cloud.h"
#include "daim_os_sys_api.h"

#define SIZE_ROW(type) printf("sizeof,%s,%zu\n", #type, sizeof(type))
#define VALUE_ROW(name) printf("constant,%s,%" PRId64 "\n", #name, (int64_t)(name))

_Static_assert(sizeof(struct packet_action_header) == 8, "action header ABI");
_Static_assert(sizeof(struct packet_action_output) == 8, "output action ABI");
_Static_assert(sizeof(struct packet_action_vlan_vid) == 8, "VLAN action ABI");
_Static_assert(sizeof(struct packet_action_dl_addr) == 8, "DL action ABI");
_Static_assert(sizeof(struct packet_action_nw_addr) == 8, "NW action ABI");
_Static_assert(sizeof(struct packet_action_tp_port) == 8, "TP action ABI");
_Static_assert(sizeof(struct packet_action_nw_tos) == 8, "TOS action ABI");

int main(void)
{
    puts("kind,name,value");
    SIZE_ROW(struct packet_action_header);
    SIZE_ROW(struct packet_action_output);
    SIZE_ROW(struct packet_action_vlan_vid);
    SIZE_ROW(struct packet_action_vlan_pcp);
    SIZE_ROW(struct packet_action_str_vlan);
    SIZE_ROW(struct packet_action_dl_addr);
    SIZE_ROW(struct packet_action_nw_addr);
    SIZE_ROW(struct packet_action_tp_port);
    SIZE_ROW(struct packet_action_nw_tos);
    SIZE_ROW(struct no_rule_packet_info);
    SIZE_ROW(struct switch_port_state);
    SIZE_ROW(struct switch_port_control);
    SIZE_ROW(struct daim_switch_link);
    SIZE_ROW(struct daim_cl_message);
    SIZE_ROW(struct daim_cl_msg_data_request_id);
    SIZE_ROW(struct daim_cl_msg_data_id);
    VALUE_ROW(DAIM_OS_VERSION);
    VALUE_ROW(DAIM_INFO_TABLE);
    VALUE_ROW(DAIM_LINK_CONFIG_TABLE);
    VALUE_ROW(PORT_FLOOD);
    VALUE_ROW(PORT_NONE);
    VALUE_ROW(DCP_REQUEST_ID);
    VALUE_ROW(DCP_REPLY_HOSTS);
    return 0;
}

