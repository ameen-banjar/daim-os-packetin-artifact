#ifndef DAIM_LEARNING_APP_H
#define DAIM_LEARNING_APP_H

#include "daim_os_api.h"
#include "daim_switch_adapter.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Registers the NO_RULE handler with DAIM Core and binds the switch adapter
   used to translate learned forwarding decisions into real OVS flows. */
int daim_learning_app_init(struct daim_switch_adapter *adapter);

/* Feeds one Packet-In event (already parsed into the spec's
   no_rule_packet_info struct) through daim_core_emit(NO_RULE, ...). Returns
   the decided output port: a physical port number, or PORT_FLOOD if the
   destination has not been learned yet on this bridge. */
uint16_t daim_learning_app_packet_in(const char *bridge, struct no_rule_packet_info *info);

void daim_learning_app_stats(uint64_t *no_rule_events, uint64_t *flows_installed, size_t *table_count);

/* Clears the learned MAC table and counters; keeps the bound adapter. */
void daim_learning_app_reset(void);

#ifdef __cplusplus
}
#endif

#endif
