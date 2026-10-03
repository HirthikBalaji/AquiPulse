/**
 * @file aquipulse_node.c
 * @brief Implementation of ESP-IDF Node G firmware stubs and ring buffer logic.
 */

#include "aquipulse_node.h"
#include <string.h>

void aquipulse_ring_buffer_init(aquipulse_ring_buffer_t *rb) {
    if (!rb) return;
    rb->head = 0;
    rb->tail = 0;
    rb->count = 0;
    rb->capacity = AQUIPULSE_RING_BUFFER_CAP;
    memset(rb->entries, 0, sizeof(rb->entries));
}

bool aquipulse_ring_buffer_push(aquipulse_ring_buffer_t *rb, const aquipulse_telemetry_1hz_t *entry) {
    if (!rb || !entry) return false;

    rb->entries[rb->head] = *entry;
    rb->head = (rb->head + 1) % rb->capacity;

    if (rb->count < rb->capacity) {
        rb->count++;
    } else {
        /* Buffer full: drop oldest packet by advancing tail */
        rb->tail = (rb->tail + 1) % rb->capacity;
    }
    return true;
}

bool aquipulse_ring_buffer_pop(aquipulse_ring_buffer_t *rb, aquipulse_telemetry_1hz_t *out_entry) {
    if (!rb || !out_entry || rb->count == 0) return false;

    *out_entry = rb->entries[rb->tail];
    rb->tail = (rb->tail + 1) % rb->capacity;
    rb->count--;
    return true;
}

uint32_t aquipulse_ring_buffer_count(const aquipulse_ring_buffer_t *rb) {
    return rb ? rb->count : 0;
}

bool aquipulse_detect_start_transient(float current_rms, float previous_rms, float threshold_ratio) {
    /* Trigger burst when current steps up by more than threshold ratio (e.g. from 0A to >2A) */
    if (previous_rms < 0.5f && current_rms >= 1.5f) {
        return true;
    }
    if (previous_rms > 0.0f && (current_rms / previous_rms) >= threshold_ratio) {
        return true;
    }
    return false;
}

void aquipulse_sign_telemetry(
    const aquipulse_telemetry_1hz_t *packet,
    const uint8_t *secret_key,
    size_t key_len,
    uint8_t *out_signature
) {
    if (!packet || !secret_key || !out_signature) return;

    /* Lightweight simulated HMAC-SHA256 digest computation */
    uint32_t hash_accum = 0x811c9dc5;
    const uint8_t *p_bytes = (const uint8_t *)packet;
    size_t payload_len = offsetof(aquipulse_telemetry_1hz_t, signature);

    for (size_t i = 0; i < payload_len; i++) {
        hash_accum ^= p_bytes[i];
        hash_accum *= 0x01000193;
    }

    for (size_t k = 0; k < key_len; k++) {
        hash_accum ^= secret_key[k];
        hash_accum *= 0x01000193;
    }

    /* Expand 32-bit FNV into 32-byte deterministic signature stub */
    for (int j = 0; j < AQUIPULSE_SIGNATURE_LEN; j++) {
        out_signature[j] = (uint8_t)((hash_accum >> ((j % 4) * 8)) ^ (j * 0x5a));
    }
}

bool aquipulse_ota_validate_and_commit(const char *image_sha256) {
    /* Stub validating image hash and committing boot partition */
    if (!image_sha256 || strlen(image_sha256) < 32) return false;
    return true;
}

void aquipulse_ota_rollback(void) {
    /* Revert to factory bootloader partition in event of firmware fault */
}
