#ifndef HEART_RATE_IF_H
#define HEART_RATE_IF_H

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdint.h>

#define HEART_RATE_MAX_RANGE_BINS          (256U)
#define HEART_RATE_DEFAULT_WINDOW_SECONDS  (20.0f)
#define HEART_RATE_MIN_BPM                 (48.0f)
#define HEART_RATE_MAX_BPM                 (180.0f)

typedef struct HeartRateDssInfo_t
{
    uint32_t frameStartTimeStamp;
    uint32_t frameStartIntCounter;
    uint16_t numRangeBins;
    uint16_t reserved0;
    float    rangeStep;
    int16_t  rangeProfileRe[HEART_RATE_MAX_RANGE_BINS];
    int16_t  rangeProfileIm[HEART_RATE_MAX_RANGE_BINS];
} HeartRateDssInfo;

typedef struct HeartRateOutput_t
{
    float    heartRateBpm;
    float    heartRateHz;
    float    confidence;
    float    sampleRateHz;
    float    rangeMeters;
    uint16_t selectedRangeBin;
    uint16_t windowLength;
    uint16_t valid;
    uint16_t reserved0;
} HeartRateOutput;

typedef struct HeartRateDebugOutput_t
{
    float    samplePowerMean;
    float    powerThreshold;
    float    bestScore;
    float    selectedScore;
    float    guideFreq;
    float    vmeGuideFreq;
    float    coarseFreq;
    float    runnerUpFreq;
    float    fineFreq;
    float    trackedFreq;
    float    guidePeakMag;
    float    coarsePeakMag;
    float    runnerUpPeakMag;
    float    finePeakMag;
    float    trackedPeakMag;
    float    signalPower;
    float    mtiAlpha;
    float    vmeAlpha;
    float    vmeLastRelErr;
    float    selectedRangeMeters;
    uint16_t bestRangeBin;
    uint16_t selectedRangeBin;
    uint16_t windowLength;
    uint16_t sampleCount;
    uint16_t isFilled;
    uint16_t valid;
    uint16_t gateChanged;
    uint16_t vmeIterations;
    uint16_t trackSelected;
    uint16_t stepLimited;
} HeartRateDebugOutput;

#ifdef __cplusplus
}
#endif

#endif /* HEART_RATE_IF_H */
