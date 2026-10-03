/**
 * @file aquipulse_node.h
 * @brief AquiPulse Node G / Node S Edge Firmware Architecture Header (ESP-IDF / C99).
 *
 * Targets ESP32-S3 with split-core CT front-end and ATECC608 secure element:
 * - 1 Hz steady-state RMS electrical telemetry
 * - 4 kHz 60-second start-burst transient capture into DMA buffer
 * - Flash ring buffer (30 days offline storage)
 * - Cryptographic packet signing (HMAC-SHA256 / ECDSA)
 * - OTA update and rollback hooks
 */

#ifndef AQUIPULSE_NODE_H
#define AQUIPULSE_NODE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define AQUIPULSE_BURST_FS_HZ         4000
#define AQUIPULSE_BURST_DURATION_SEC  60
#define AQUIPULSE_BURST_TOTAL_SAMPLES (AQUIPULSE_BURST_FS_HZ * AQUIPULSE_BURST_DURATION_SEC)
#define AQUIPULSE_RING_BUFFER_CAP     2048
#define AQUIPULSE_SIGNATURE_LEN       32

/**
 * @brief 1 Hz Steady-State Electrical Telemetry Packet.
 */
typedef struct {
    char pump_id[32];
    uint64_t timestamp_ms;
    float v_rms;
    float i_rms;
    float pf;
    float p_kw;
    float freq_hz;
    uint8_t signature[AQUIPULSE_SIGNATURE_LEN];
} aquipulse_telemetry_1hz_t;

/**
 * @brief 4 kHz Start-Burst Capture Header and Buffer.
 */
typedef struct {
    char pump_id[32];
    uint64_t start_timestamp_ms;
    uint32_t sample_rate_hz;
    uint32_t sample_count;
    int16_t samples[AQUIPULSE_BURST_TOTAL_SAMPLES];
    uint8_t signature[AQUIPULSE_SIGNATURE_LEN];
} aquipulse_burst_record_t;

/**
 * @brief Circular Flash Ring Buffer State.
 */
typedef struct {
    uint32_t head;
    uint32_t tail;
    uint32_t count;
    uint32_t capacity;
    aquipulse_telemetry_1hz_t entries[AQUIPULSE_RING_BUFFER_CAP];
} aquipulse_ring_buffer_t;

/* Ring Buffer Functions */
void aquipulse_ring_buffer_init(aquipulse_ring_buffer_t *rb);
bool aquipulse_ring_buffer_push(aquipulse_ring_buffer_t *rb, const aquipulse_telemetry_1hz_t *entry);
bool aquipulse_ring_buffer_pop(aquipulse_ring_buffer_t *rb, aquipulse_telemetry_1hz_t *out_entry);
uint32_t aquipulse_ring_buffer_count(const aquipulse_ring_buffer_t *rb);

/* Cryptographic Signing */
void aquipulse_sign_telemetry(
    const aquipulse_telemetry_1hz_t *packet,
    const uint8_t *secret_key,
    size_t key_len,
    uint8_t *out_signature
);

/* 4 kHz Burst Acquisition Trigger */
bool aquipulse_detect_start_transient(float current_rms, float previous_rms, float threshold_ratio);

/* OTA Hooks */
bool aquipulse_ota_validate_and_commit(const char *image_sha256);
void aquipulse_ota_rollback(void);

#ifdef __cplusplus
}
#endif

#endif /* AQUIPULSE_NODE_H */
