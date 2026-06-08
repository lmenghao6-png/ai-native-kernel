#pragma once
#include <stdint.h>
#include <stdbool.h>
struct task;
typedef struct { uint64_t admissions, dispatches, completions, failures, timer_ticks, runtime_ticks, preempt_requests, current_task_id, last_task_id, runnable_depth, runnable_peak, blocked_depth, blocked_peak, current_slice_ticks, last_run_ticks, peak_slice_ticks; uint32_t ready, time_slice_ticks, last_stop_reason; uint64_t last_stop_vector; } scheduler_stats_t;
enum task_stop_reason { STOP_NONE, STOP_BLOCKED, STOP_PREEMPTED, STOP_EXITED, STOP_YIELD, STOP_FAILED };
void scheduler_init(uint32_t t);
void scheduler_submit(struct task *t);
struct task *scheduler_pick_next(struct task *c, enum task_stop_reason r);
void scheduler_tick(void);
scheduler_stats_t scheduler_get_stats(void);
