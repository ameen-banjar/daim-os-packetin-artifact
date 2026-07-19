#include "daim_core.h"

#include <assert.h>
#include <pthread.h>
#include <stdint.h>

enum { THREADS = 4, WRITES_PER_THREAD = 1000 };

static void *writer(void *argument)
{
    uintptr_t thread_no = (uintptr_t)argument;
    int i;
    for (i = 0; i < WRITES_PER_THREAD; ++i) {
        struct switch_link_config_table_entry entry = {0};
        entry.id = (uint64_t)(thread_no * WRITES_PER_THREAD + (uintptr_t)i + 1);
        entry.link_state = LINK_UP;
        entry.link_speed = 1000000000ULL;
        entry.weight = (uint8_t)(i % 101);
        assert(daim_table_write(DAIM_LINK_CONFIG_TABLE, &entry, sizeof(entry), ADD) == DAIM_CORE_OK);
    }
    return NULL;
}

int main(void)
{
    pthread_t threads[THREADS];
    uintptr_t i;
    assert(daim_init() == DAIM_CORE_OK);
    for (i = 0; i < THREADS; ++i) assert(pthread_create(&threads[i], NULL, writer, (void *)i) == 0);
    for (i = 0; i < THREADS; ++i) assert(pthread_join(threads[i], NULL) == 0);
    assert(daim_core_table_count(DAIM_LINK_CONFIG_TABLE) == THREADS * WRITES_PER_THREAD);
    assert(daim_core_generation() == THREADS * WRITES_PER_THREAD);
    daim_quit();
    return 0;
}
