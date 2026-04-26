#ifndef HEART_RATE_DSS_PROC_H
#define HEART_RATE_DSS_PROC_H

#include <math.h>
#include <string.h>

#define HEART_RATE_MAX_WINDOW_SAMPLES    256U
#define HEART_RATE_RANGE_BIN_SKIP        3U
#define HEART_RATE_BANDPASS_ORDER        3U
#define HEART_RATE_GUIDE_FREQ_MIN_HZ     1.0f
#define HEART_RATE_GUIDE_FILTER_MAX_HZ   2.0f
#define HEART_RATE_GUIDE_FREQ_MAX_HZ     3.0f
#define HEART_RATE_FINE_SEARCH_HALF_BINS 2U
#define HEART_RATE_VME_ALPHA             100.0f
#define HEART_RATE_TARGET_SAMPLE_RATE_HZ 10.0f
#define HEART_RATE_ESTIMATE_STEP_SECONDS 0.5f
#define HEART_RATE_TRACK_HALF_SPAN_HZ    0.08f
#define HEART_RATE_TRACK_KEEP_RATIO      0.75f
#define HEART_RATE_MAX_STEP_HZ           0.010f
#define HEART_RATE_SWITCH_GUARD_HZ       0.05f
#define HEART_RATE_SWITCH_CONFIRM_TOL_HZ 0.03f
#define HEART_RATE_SWITCH_CONFIRM_COUNT  4U
#define HEART_RATE_DSS_TIMESTAMP_HZ      600000000.0f
#define HEART_RATE_TWO_PI                6.28318530718f

typedef struct HeartRateDssCtx_t
{
    float    energyAccum[HEART_RATE_MAX_RANGE_BINS];
    float    rangeMeanRe[HEART_RATE_MAX_RANGE_BINS];
    float    rangeMeanIm[HEART_RATE_MAX_RANGE_BINS];
    float    slowTimeRe[HEART_RATE_MAX_WINDOW_SAMPLES];
    float    slowTimeIm[HEART_RATE_MAX_WINDOW_SAMPLES];
    uint16_t numRangeBins;
    uint16_t windowLength;
    uint16_t sampleCount;
    uint16_t nextIndex;
    uint16_t slowTimeAccumCount;
    uint16_t estimateStrideSamples;
    uint16_t samplesSinceEstimate;
    uint16_t selectedRangeBin;
    uint8_t  isFilled;
    uint8_t  rateConfigLocked;
    uint16_t reserved0;
    float    frameRateHz;
    float    sampleRateHz;
    float    targetSampleRateHz;
    float    rangeStep;
    float    slowTimeAccumRe;
    float    slowTimeAccumIm;
    float    trackedHeartRateHz;
    float    pendingSwitchHeartRateHz;
    uint32_t prevFrameStartTimeStamp;
    uint32_t snapshotSeq;
    uint16_t trackedHeartRateValid;
    uint16_t pendingSwitchCount;
    HeartRateOutput      output;
    HeartRateDebugOutput debugOutput;
} HeartRateDssCtx;

typedef struct HeartRateDssScratch_t
{
    float seriesRe[HEART_RATE_MAX_WINDOW_SAMPLES];
    float seriesIm[HEART_RATE_MAX_WINDOW_SAMPLES];
    float phaseRaw[HEART_RATE_MAX_WINDOW_SAMPLES];
    float phaseFilt[HEART_RATE_MAX_WINDOW_SAMPLES];
    float rhoRaw[HEART_RATE_MAX_WINDOW_SAMPLES];
    float rhoMed[HEART_RATE_MAX_WINDOW_SAMPLES];
    float psi[HEART_RATE_MAX_WINDOW_SAMPLES];
    float heartSignal[HEART_RATE_MAX_WINDOW_SAMPLES];
    float fftRe[HEART_RATE_MAX_WINDOW_SAMPLES];
    float fftIm[HEART_RATE_MAX_WINDOW_SAMPLES];
    float dHatRe[HEART_RATE_MAX_WINDOW_SAMPLES];
    float dHatIm[HEART_RATE_MAX_WINDOW_SAMPLES];
    float dHatOldRe[HEART_RATE_MAX_WINDOW_SAMPLES];
    float dHatOldIm[HEART_RATE_MAX_WINDOW_SAMPLES];
} HeartRateDssScratch;

static float HeartRateDss_magSq(float re, float im)
{
    return ((re * re) + (im * im));
}

static float HeartRateDss_median3(float a, float b, float c)
{
    float tmp;

    if (a > b)
    {
        tmp = a;
        a   = b;
        b   = tmp;
    }
    if (b > c)
    {
        tmp = b;
        b   = c;
        c   = tmp;
    }
    if (a > b)
    {
        tmp = a;
        a   = b;
        b   = tmp;
    }
    return b;
}

static void HeartRateDss_resetCtx(HeartRateDssCtx *ctx)
{
    float    frameRateHz;
    float    sampleRateHz;
    float    targetSampleRateHz;
    float    rangeStep;
    uint16_t windowLength;
    uint16_t numRangeBins;
    uint16_t estimateStrideSamples;
    uint32_t prevFrameStartTimeStamp;
    uint32_t snapshotSeq;
    uint8_t  rateConfigLocked;

    frameRateHz             = ctx->frameRateHz;
    sampleRateHz            = ctx->sampleRateHz;
    targetSampleRateHz      = ctx->targetSampleRateHz;
    rangeStep               = ctx->rangeStep;
    windowLength            = ctx->windowLength;
    numRangeBins            = ctx->numRangeBins;
    estimateStrideSamples   = ctx->estimateStrideSamples;
    prevFrameStartTimeStamp = ctx->prevFrameStartTimeStamp;
    snapshotSeq             = ctx->snapshotSeq;
    rateConfigLocked        = ctx->rateConfigLocked;

    memset((void *)ctx, 0, sizeof(HeartRateDssCtx));

    ctx->frameRateHz             = frameRateHz;
    ctx->sampleRateHz            = sampleRateHz;
    ctx->targetSampleRateHz      = targetSampleRateHz;
    ctx->rangeStep               = rangeStep;
    ctx->windowLength            = windowLength;
    ctx->numRangeBins            = numRangeBins;
    ctx->estimateStrideSamples   = estimateStrideSamples;
    ctx->prevFrameStartTimeStamp = prevFrameStartTimeStamp;
    ctx->snapshotSeq             = snapshotSeq;
    ctx->rateConfigLocked        = rateConfigLocked;
    ctx->selectedRangeBin        = 0xFFFFU;
    ctx->output.selectedRangeBin = 0xFFFFU;
    ctx->output.sampleRateHz     = sampleRateHz;
    ctx->output.windowLength     = windowLength;
}

static void HeartRateDss_clearEstimate(HeartRateDssCtx *ctx)
{
    ctx->output.heartRateBpm = 0.0f;
    ctx->output.heartRateHz  = 0.0f;
    ctx->output.confidence   = 0.0f;
    ctx->output.valid        = 0U;

    ctx->debugOutput.guideFreq               = 0.0f;
    ctx->debugOutput.vmeGuideFreq            = 0.0f;
    ctx->debugOutput.coarseFreq              = 0.0f;
    ctx->debugOutput.runnerUpFreq            = 0.0f;
    ctx->debugOutput.fineFreq                = 0.0f;
    ctx->debugOutput.trackedFreq             = 0.0f;
    ctx->debugOutput.coarsePeakMag           = 0.0f;
    ctx->debugOutput.runnerUpPeakMag         = 0.0f;
    ctx->debugOutput.finePeakMag             = 0.0f;
    ctx->debugOutput.trackedPeakMag          = 0.0f;
    ctx->debugOutput.signalPower             = 0.0f;
    ctx->debugOutput.competitionRatio        = 0.0f;
    ctx->debugOutput.guideVmeGapHz           = 0.0f;
    ctx->debugOutput.coarseFineGapHz         = 0.0f;
    ctx->debugOutput.trackedFineGapHz        = 0.0f;
    ctx->debugOutput.vmeLastRelErr           = 0.0f;
    ctx->debugOutput.estimateSeq             = 0U;
    ctx->debugOutput.interFrameProcTimeUsec  = 0U;
    ctx->debugOutput.interFrameProcMarginUsec = 0U;
    ctx->debugOutput.txWriteTimeUsec         = 0U;
    ctx->debugOutput.txOverwriteCount        = 0U;
    ctx->debugOutput.vmeIterations           = 0U;
    ctx->debugOutput.trackSelected           = 0U;
    ctx->debugOutput.stepLimited             = 0U;
    ctx->debugOutput.valid                   = 0U;
}

static void HeartRateDss_publishResult(const HeartRateDssCtx *ctx, HeartRateDssResult *outResult)
{
    outResult->snapshotSeq = ctx->snapshotSeq;
    outResult->reserved0   = 0U;
    outResult->output      = ctx->output;
    outResult->debugOutput = ctx->debugOutput;
}

static void HeartRateDss_configureCtx(HeartRateDssCtx *ctx,
                                      uint16_t         numRangeBins,
                                      float            rangeStep,
                                      float            frameRateHz)
{
    float    targetSampleRateHz;
    float    sampleRateHz;
    uint16_t estimateStrideSamples;
    uint16_t windowLength;
    uint8_t  resetCtx;

    targetSampleRateHz = ctx->targetSampleRateHz;
    if (targetSampleRateHz <= 0.0f)
    {
        targetSampleRateHz = HEART_RATE_TARGET_SAMPLE_RATE_HZ;
    }

    if (frameRateHz > 0.0f)
    {
        sampleRateHz = frameRateHz;
    }
    else
    {
        sampleRateHz = targetSampleRateHz;
    }

    if ((targetSampleRateHz > 0.0f) && (sampleRateHz > targetSampleRateHz))
    {
        sampleRateHz = targetSampleRateHz;
    }
    if (sampleRateHz <= 0.0f)
    {
        sampleRateHz = 1.0f;
    }

    estimateStrideSamples =
        (uint16_t)((HEART_RATE_ESTIMATE_STEP_SECONDS * sampleRateHz) + 0.5f);
    if (estimateStrideSamples == 0U)
    {
        estimateStrideSamples = 1U;
    }

    windowLength =
        (uint16_t)((HEART_RATE_DEFAULT_WINDOW_SECONDS * sampleRateHz) + 0.5f);
    if (windowLength == 0U)
    {
        windowLength = 1U;
    }
    if (windowLength > HEART_RATE_MAX_WINDOW_SAMPLES)
    {
        windowLength = HEART_RATE_MAX_WINDOW_SAMPLES;
    }

    resetCtx = 0U;
    if ((ctx->numRangeBins != numRangeBins) ||
        (fabsf(ctx->rangeStep - rangeStep) > 1.0e-6f))
    {
        ctx->rateConfigLocked = 0U;
        resetCtx = 1U;
    }
    else if ((ctx->rateConfigLocked == 0U) &&
             ((fabsf(ctx->sampleRateHz - sampleRateHz) > 1.0e-3f) ||
              (ctx->windowLength != windowLength) ||
              (ctx->estimateStrideSamples != estimateStrideSamples)))
    {
        resetCtx = 1U;
    }

    if (resetCtx != 0U)
    {
        ctx->numRangeBins          = numRangeBins;
        ctx->rangeStep             = rangeStep;
        ctx->frameRateHz           = frameRateHz;
        ctx->sampleRateHz          = sampleRateHz;
        ctx->targetSampleRateHz    = targetSampleRateHz;
        ctx->windowLength          = windowLength;
        ctx->estimateStrideSamples = estimateStrideSamples;
        ctx->rateConfigLocked      = (uint8_t)(frameRateHz > 0.0f);
        HeartRateDss_resetCtx(ctx);
    }
    else
    {
        ctx->frameRateHz         = frameRateHz;
        ctx->targetSampleRateHz  = targetSampleRateHz;
        ctx->output.sampleRateHz = ctx->sampleRateHz;
        ctx->output.windowLength = ctx->windowLength;
    }
}

static void HeartRateDss_pushSlowTimeSample(HeartRateDssCtx *ctx, float sampleRe, float sampleIm)
{
    if (ctx->windowLength == 0U)
    {
        return;
    }

    ctx->slowTimeRe[ctx->nextIndex] = sampleRe;
    ctx->slowTimeIm[ctx->nextIndex] = sampleIm;
    ctx->nextIndex = (uint16_t)((ctx->nextIndex + 1U) % ctx->windowLength);

    if (ctx->sampleCount < ctx->windowLength)
    {
        ctx->sampleCount++;
    }
    if (ctx->sampleCount >= ctx->windowLength)
    {
        ctx->isFilled = 1U;
    }
}

static void HeartRateDss_computeBandpassBiquad(float fs,
                                               float fLow,
                                               float fHigh,
                                               float *b0,
                                               float *b1,
                                               float *b2,
                                               float *a1,
                                               float *a2)
{
    float centerFreq;
    float bandwidth;
    float qFactor;
    float omega;
    float alpha;
    float cosOmega;
    float a0;

    if ((fs <= 0.0f) || (fLow <= 0.0f) || (fHigh <= fLow))
    {
        *b0 = 1.0f;
        *b1 = 0.0f;
        *b2 = 0.0f;
        *a1 = 0.0f;
        *a2 = 0.0f;
        return;
    }

    centerFreq = sqrtf(fLow * fHigh);
    bandwidth  = fHigh - fLow;
    qFactor    = centerFreq / bandwidth;
    omega      = HEART_RATE_TWO_PI * centerFreq / fs;
    alpha      = sinf(omega) / (2.0f * qFactor);
    cosOmega   = cosf(omega);
    a0         = 1.0f + alpha;

    *b0 = alpha / a0;
    *b1 = 0.0f;
    *b2 = -alpha / a0;
    *a1 = (-2.0f * cosOmega) / a0;
    *a2 = (1.0f - alpha) / a0;
}

static void HeartRateDss_applyBiquad(const float *input,
                                     float       *output,
                                     uint16_t     length,
                                     float        b0,
                                     float        b1,
                                     float        b2,
                                     float        a1,
                                     float        a2)
{
    uint16_t sampleIdx;
    float    x1;
    float    x2;
    float    y1;
    float    y2;
    float    x0;
    float    y0;

    x1 = 0.0f;
    x2 = 0.0f;
    y1 = 0.0f;
    y2 = 0.0f;

    for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
    {
        x0                = input[sampleIdx];
        y0                = (b0 * x0) + (b1 * x1) + (b2 * x2) - (a1 * y1) - (a2 * y2);
        output[sampleIdx] = y0;

        x2 = x1;
        x1 = x0;
        y2 = y1;
        y1 = y0;
    }
}

static void HeartRateDss_applyBiquadForwardBackward(const float *input,
                                                    float       *scratch,
                                                    float       *output,
                                                    uint16_t     length,
                                                    float        b0,
                                                    float        b1,
                                                    float        b2,
                                                    float        a1,
                                                    float        a2)
{
    uint16_t sampleIdx;

    HeartRateDss_applyBiquad(input, scratch, length, b0, b1, b2, a1, a2);

    for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
    {
        output[sampleIdx] = scratch[(length - 1U) - sampleIdx];
    }

    HeartRateDss_applyBiquad(output, scratch, length, b0, b1, b2, a1, a2);

    for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
    {
        output[sampleIdx] = scratch[(length - 1U) - sampleIdx];
    }
}

static float HeartRateDss_findPeakFrequencyWithRunnerUp(const float *signal,
                                                        uint16_t     length,
                                                        float        fs,
                                                        float        fMin,
                                                        float        fMax,
                                                        uint16_t     numGrid,
                                                        float       *peakMagOut,
                                                        float       *runnerUpFreqOut,
                                                        float       *runnerUpMagOut)
{
    uint16_t gridIdx;
    uint16_t sampleIdx;
    float    step;
    float    bestMag;
    float    bestFreq;
    float    runnerUpMag;
    float    runnerUpFreq;
    float    exclusionHz;
    float    freq;
    float    angleStep;
    float    cosStep;
    float    sinStep;
    float    cosCurr;
    float    sinCurr;
    float    tmp;
    float    sumRe;
    float    sumIm;
    float    mag;

    if ((length == 0U) || (fs <= 0.0f) || (fMax <= fMin))
    {
        if (peakMagOut != NULL)
        {
            *peakMagOut = 0.0f;
        }
        if (runnerUpFreqOut != NULL)
        {
            *runnerUpFreqOut = 0.0f;
        }
        if (runnerUpMagOut != NULL)
        {
            *runnerUpMagOut = 0.0f;
        }
        return fMin;
    }

    if (numGrid < 2U)
    {
        numGrid = 2U;
    }

    step         = (fMax - fMin) / (float)(numGrid - 1U);
    bestMag      = 0.0f;
    bestFreq     = fMin;
    runnerUpMag  = 0.0f;
    runnerUpFreq = fMin;

    for (gridIdx = 0U; gridIdx < numGrid; gridIdx++)
    {
        freq      = fMin + ((float)gridIdx * step);
        angleStep = -HEART_RATE_TWO_PI * freq / fs;
        cosStep   = cosf(angleStep);
        sinStep   = sinf(angleStep);
        cosCurr   = 1.0f;
        sinCurr   = 0.0f;
        sumRe     = 0.0f;
        sumIm     = 0.0f;

        for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
        {
            sumRe += signal[sampleIdx] * cosCurr;
            sumIm += signal[sampleIdx] * sinCurr;

            tmp     = (cosCurr * cosStep) - (sinCurr * sinStep);
            sinCurr = (cosCurr * sinStep) + (sinCurr * cosStep);
            cosCurr = tmp;
        }

        mag = (sumRe * sumRe) + (sumIm * sumIm);
        if (mag > bestMag)
        {
            bestMag  = mag;
            bestFreq = freq;
        }
    }

    if ((runnerUpFreqOut != NULL) || (runnerUpMagOut != NULL))
    {
        exclusionHz = 3.0f * step;
        for (gridIdx = 0U; gridIdx < numGrid; gridIdx++)
        {
            freq = fMin + ((float)gridIdx * step);
            if (fabsf(freq - bestFreq) <= exclusionHz)
            {
                continue;
            }

            angleStep = -HEART_RATE_TWO_PI * freq / fs;
            cosStep   = cosf(angleStep);
            sinStep   = sinf(angleStep);
            cosCurr   = 1.0f;
            sinCurr   = 0.0f;
            sumRe     = 0.0f;
            sumIm     = 0.0f;

            for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
            {
                sumRe += signal[sampleIdx] * cosCurr;
                sumIm += signal[sampleIdx] * sinCurr;

                tmp     = (cosCurr * cosStep) - (sinCurr * sinStep);
                sinCurr = (cosCurr * sinStep) + (sinCurr * cosStep);
                cosCurr = tmp;
            }

            mag = (sumRe * sumRe) + (sumIm * sumIm);
            if (mag > runnerUpMag)
            {
                runnerUpMag  = mag;
                runnerUpFreq = freq;
            }
        }
    }

    if (peakMagOut != NULL)
    {
        *peakMagOut = bestMag;
    }
    if (runnerUpFreqOut != NULL)
    {
        *runnerUpFreqOut = runnerUpFreq;
    }
    if (runnerUpMagOut != NULL)
    {
        *runnerUpMagOut = runnerUpMag;
    }

    return bestFreq;
}

static float HeartRateDss_findPeakFrequency(const float *signal,
                                            uint16_t     length,
                                            float        fs,
                                            float        fMin,
                                            float        fMax,
                                            uint16_t     numGrid,
                                            float       *peakMagOut)
{
    return HeartRateDss_findPeakFrequencyWithRunnerUp(signal,
                                                      length,
                                                      fs,
                                                      fMin,
                                                      fMax,
                                                      numGrid,
                                                      peakMagOut,
                                                      NULL,
                                                      NULL);
}

static float HeartRateDss_runVME(const float         *phaseRaw,
                                 uint16_t             length,
                                 float                fs,
                                 float                guideFreq,
                                 HeartRateDssScratch *scratch,
                                 float               *heartSignalOut,
                                 uint16_t            *iterationsOut,
                                 float               *relErrOut)
{
    uint16_t sampleIdx;
    uint16_t freqIdx;
    uint16_t iterIdx;
    uint16_t halfLength;
    float    omegaGuide;
    float    freqOmega;
    float    diffOmega;
    float    diffOmega2;
    float    termAlpha;
    float    denominator;
    float    numeratorOmega;
    float    denominatorOmega;
    float    powerVal;
    float    errNum;
    float    errDen;
    float    diffRe;
    float    diffIm;
    float    relErr;
    float    angleStep;
    float    cosStep;
    float    sinStep;
    float    cosCurr;
    float    sinCurr;
    float    tmp;
    float    sumRe;
    float    alpha;

    alpha  = HEART_RATE_VME_ALPHA;
    relErr = 0.0f;

    scratch->psi[0] = 0.0f;
    for (sampleIdx = 1U; sampleIdx < length; sampleIdx++)
    {
        scratch->psi[sampleIdx] = phaseRaw[sampleIdx] - phaseRaw[sampleIdx - 1U];
    }

    for (freqIdx = 0U; freqIdx < length; freqIdx++)
    {
        angleStep = -HEART_RATE_TWO_PI * (float)freqIdx / (float)length;
        cosStep   = cosf(angleStep);
        sinStep   = sinf(angleStep);
        cosCurr   = 1.0f;
        sinCurr   = 0.0f;
        scratch->fftRe[freqIdx] = 0.0f;
        scratch->fftIm[freqIdx] = 0.0f;

        for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
        {
            scratch->fftRe[freqIdx] += scratch->psi[sampleIdx] * cosCurr;
            scratch->fftIm[freqIdx] += scratch->psi[sampleIdx] * sinCurr;

            tmp     = (cosCurr * cosStep) - (sinCurr * sinStep);
            sinCurr = (cosCurr * sinStep) + (sinCurr * cosStep);
            cosCurr = tmp;
        }

        scratch->dHatRe[freqIdx]    = 0.0f;
        scratch->dHatIm[freqIdx]    = 0.0f;
        scratch->dHatOldRe[freqIdx] = 0.0f;
        scratch->dHatOldIm[freqIdx] = 0.0f;
    }

    omegaGuide = HEART_RATE_TWO_PI * guideFreq;
    halfLength = length / 2U;

    for (iterIdx = 0U; iterIdx < 40U; iterIdx++)
    {
        for (freqIdx = 0U; freqIdx < length; freqIdx++)
        {
            freqOmega   = HEART_RATE_TWO_PI * fs * ((float)freqIdx / (float)length);
            diffOmega   = freqOmega - omegaGuide;
            diffOmega2  = diffOmega * diffOmega;
            termAlpha   = alpha * alpha * diffOmega2 * diffOmega2;
            denominator = (1.0f + termAlpha) * (1.0f + (2.0f * alpha * diffOmega2));
            scratch->dHatRe[freqIdx] =
                (scratch->fftRe[freqIdx] + (termAlpha * scratch->dHatOldRe[freqIdx])) / denominator;
            scratch->dHatIm[freqIdx] =
                (scratch->fftIm[freqIdx] + (termAlpha * scratch->dHatOldIm[freqIdx])) / denominator;
        }

        numeratorOmega   = 0.0f;
        denominatorOmega = 0.0f;
        for (freqIdx = 1U; freqIdx < halfLength; freqIdx++)
        {
            powerVal = HeartRateDss_magSq(scratch->dHatRe[freqIdx], scratch->dHatIm[freqIdx]);
            numeratorOmega += (HEART_RATE_TWO_PI * fs * ((float)freqIdx / (float)length)) * powerVal;
            denominatorOmega += powerVal;
        }

        if (denominatorOmega > 0.0f)
        {
            omegaGuide = numeratorOmega / denominatorOmega;
        }

        errNum = 0.0f;
        errDen = 0.0f;
        for (freqIdx = 0U; freqIdx < length; freqIdx++)
        {
            diffRe = scratch->dHatRe[freqIdx] - scratch->dHatOldRe[freqIdx];
            diffIm = scratch->dHatIm[freqIdx] - scratch->dHatOldIm[freqIdx];
            errNum += HeartRateDss_magSq(diffRe, diffIm);
            errDen += HeartRateDss_magSq(scratch->dHatOldRe[freqIdx], scratch->dHatOldIm[freqIdx]);

            scratch->dHatOldRe[freqIdx] = scratch->dHatRe[freqIdx];
            scratch->dHatOldIm[freqIdx] = scratch->dHatIm[freqIdx];
        }

        relErr = errNum / (errDen + 1.0e-6f);
        if ((iterIdx > 0U) && (relErr < 1.0e-4f))
        {
            break;
        }
    }

    for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
    {
        angleStep = HEART_RATE_TWO_PI * (float)sampleIdx / (float)length;
        cosStep   = cosf(angleStep);
        sinStep   = sinf(angleStep);
        cosCurr   = 1.0f;
        sinCurr   = 0.0f;
        sumRe     = 0.0f;

        for (freqIdx = 0U; freqIdx < length; freqIdx++)
        {
            sumRe += (scratch->dHatRe[freqIdx] * cosCurr) - (scratch->dHatIm[freqIdx] * sinCurr);

            tmp     = (cosCurr * cosStep) - (sinCurr * sinStep);
            sinCurr = (cosCurr * sinStep) + (sinCurr * cosStep);
            cosCurr = tmp;
        }

        heartSignalOut[sampleIdx] = sumRe / (float)length;
    }

    if (length > 1U)
    {
        tmp = heartSignalOut[length - 1U];
        for (sampleIdx = (uint16_t)(length - 1U); sampleIdx > 0U; sampleIdx--)
        {
            heartSignalOut[sampleIdx] = heartSignalOut[sampleIdx - 1U];
        }
        heartSignalOut[0] = tmp;
    }

    if (iterationsOut != NULL)
    {
        *iterationsOut = (uint16_t)(iterIdx + 1U);
    }
    if (relErrOut != NULL)
    {
        *relErrOut = relErr;
    }

    return (omegaGuide / HEART_RATE_TWO_PI);
}

static void HeartRateDss_estimateForWindow(HeartRateDssCtx     *ctx,
                                           HeartRateDssScratch *scratch,
                                           volatile uint32_t   *estimateSeq)
{
    uint16_t sampleIdx;
    uint16_t histIdx;
    uint16_t length;
    float    samplePowerMean;
    float    powerThreshold;
    float    dI;
    float    dQ;
    float    denominator;
    float    b0;
    float    b1;
    float    b2;
    float    a1;
    float    a2;
    float    coarsePeakMag;
    float    finePeakMag;
    float    runnerUpPeakMag;
    float    guideFreq;
    float    vmeGuideFreq;
    float    coarseFreq;
    float    runnerUpFreq;
    float    fineFreq;
    float    trackedFreq;
    float    trackedPeakMag;
    float    trackedStart;
    float    trackedEnd;
    float    coarseDf;
    float    fineStart;
    float    fineEnd;
    float    signalPower;
    float    vmeLastRelErr;
    float    candidateFreq;
    float    candidatePeakMag;
    uint16_t vmeIterations;
    uint16_t trackSelected;
    uint16_t stepLimited;

    length = ctx->windowLength;
    if ((ctx->sampleCount < length) || (length == 0U) || (ctx->sampleRateHz <= 0.0f))
    {
        HeartRateDss_clearEstimate(ctx);
        return;
    }

    runnerUpPeakMag  = 0.0f;
    runnerUpFreq     = 0.0f;
    trackedFreq      = ctx->trackedHeartRateHz;
    trackedPeakMag   = 0.0f;
    vmeGuideFreq     = 0.0f;
    vmeLastRelErr    = 0.0f;
    vmeIterations    = 0U;
    trackSelected    = 0U;
    stepLimited      = 0U;
    candidateFreq    = 0.0f;
    candidatePeakMag = 0.0f;

    if (ctx->isFilled != 0U)
    {
        for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
        {
            histIdx = (uint16_t)((ctx->nextIndex + sampleIdx) % length);
            scratch->seriesRe[sampleIdx] = ctx->slowTimeRe[histIdx];
            scratch->seriesIm[sampleIdx] = ctx->slowTimeIm[histIdx];
        }
    }
    else
    {
        for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
        {
            scratch->seriesRe[sampleIdx] = ctx->slowTimeRe[sampleIdx];
            scratch->seriesIm[sampleIdx] = ctx->slowTimeIm[sampleIdx];
        }
    }

    samplePowerMean = 0.0f;
    for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
    {
        samplePowerMean += HeartRateDss_magSq(scratch->seriesRe[sampleIdx], scratch->seriesIm[sampleIdx]);
    }
    samplePowerMean /= (float)length;
    powerThreshold = 0.5f * samplePowerMean;
    if (powerThreshold < 1.0f)
    {
        powerThreshold = 1.0f;
    }

    scratch->rhoRaw[0] = 0.0f;
    for (sampleIdx = 1U; sampleIdx < length; sampleIdx++)
    {
        dI = scratch->seriesRe[sampleIdx] - scratch->seriesRe[sampleIdx - 1U];
        dQ = scratch->seriesIm[sampleIdx] - scratch->seriesIm[sampleIdx - 1U];
        denominator = HeartRateDss_magSq(scratch->seriesRe[sampleIdx], scratch->seriesIm[sampleIdx]);
        if (denominator < powerThreshold)
        {
            denominator = powerThreshold;
        }

        scratch->rhoRaw[sampleIdx] =
            ((scratch->seriesRe[sampleIdx] * dQ) - (scratch->seriesIm[sampleIdx] * dI)) / denominator;
    }

    scratch->rhoMed[0] = scratch->rhoRaw[0];
    for (sampleIdx = 1U; sampleIdx < (length - 1U); sampleIdx++)
    {
        scratch->rhoMed[sampleIdx] =
            HeartRateDss_median3(scratch->rhoRaw[sampleIdx - 1U],
                                 scratch->rhoRaw[sampleIdx],
                                 scratch->rhoRaw[sampleIdx + 1U]);
    }
    if (length > 1U)
    {
        scratch->rhoMed[length - 1U] = scratch->rhoRaw[length - 1U];
    }

    scratch->phaseRaw[0] = scratch->rhoMed[0];
    for (sampleIdx = 1U; sampleIdx < length; sampleIdx++)
    {
        scratch->phaseRaw[sampleIdx] = scratch->phaseRaw[sampleIdx - 1U] + scratch->rhoMed[sampleIdx];
    }

    HeartRateDss_computeBandpassBiquad(ctx->sampleRateHz,
                                       HEART_RATE_GUIDE_FREQ_MIN_HZ,
                                       HEART_RATE_GUIDE_FILTER_MAX_HZ,
                                       &b0,
                                       &b1,
                                       &b2,
                                       &a1,
                                       &a2);
    HeartRateDss_applyBiquadForwardBackward(scratch->phaseRaw,
                                            scratch->seriesRe,
                                            scratch->phaseFilt,
                                            length,
                                            b0,
                                            b1,
                                            b2,
                                            a1,
                                            a2);

    coarseFreq = HeartRateDss_findPeakFrequency(scratch->phaseFilt,
                                                length,
                                                ctx->sampleRateHz,
                                                HEART_RATE_GUIDE_FREQ_MIN_HZ,
                                                HEART_RATE_GUIDE_FILTER_MAX_HZ,
                                                length,
                                                NULL);
    guideFreq = coarseFreq;

    vmeGuideFreq = HeartRateDss_runVME(scratch->phaseRaw,
                                       length,
                                       ctx->sampleRateHz,
                                       coarseFreq,
                                       scratch,
                                       scratch->heartSignal,
                                       &vmeIterations,
                                       &vmeLastRelErr);

    coarseFreq = HeartRateDss_findPeakFrequencyWithRunnerUp(scratch->heartSignal,
                                                            length,
                                                            ctx->sampleRateHz,
                                                            HEART_RATE_GUIDE_FREQ_MIN_HZ,
                                                            HEART_RATE_GUIDE_FREQ_MAX_HZ,
                                                            length,
                                                            &coarsePeakMag,
                                                            &runnerUpFreq,
                                                            &runnerUpPeakMag);

    coarseDf  = (HEART_RATE_GUIDE_FREQ_MAX_HZ - HEART_RATE_GUIDE_FREQ_MIN_HZ) / (float)length;
    fineStart = coarseFreq - ((float)HEART_RATE_FINE_SEARCH_HALF_BINS * coarseDf);
    fineEnd   = coarseFreq + ((float)HEART_RATE_FINE_SEARCH_HALF_BINS * coarseDf);

    if (fineStart < HEART_RATE_GUIDE_FREQ_MIN_HZ)
    {
        fineStart = HEART_RATE_GUIDE_FREQ_MIN_HZ;
    }
    if (fineEnd > HEART_RATE_GUIDE_FREQ_MAX_HZ)
    {
        fineEnd = HEART_RATE_GUIDE_FREQ_MAX_HZ;
    }

    fineFreq = HeartRateDss_findPeakFrequency(scratch->heartSignal,
                                              length,
                                              ctx->sampleRateHz,
                                              fineStart,
                                              fineEnd,
                                              length,
                                              &finePeakMag);
    candidateFreq    = fineFreq;
    candidatePeakMag = finePeakMag;

    if (ctx->trackedHeartRateValid != 0U)
    {
        trackedStart = ctx->trackedHeartRateHz - HEART_RATE_TRACK_HALF_SPAN_HZ;
        trackedEnd   = ctx->trackedHeartRateHz + HEART_RATE_TRACK_HALF_SPAN_HZ;
        if (trackedStart < HEART_RATE_GUIDE_FREQ_MIN_HZ)
        {
            trackedStart = HEART_RATE_GUIDE_FREQ_MIN_HZ;
        }
        if (trackedEnd > HEART_RATE_GUIDE_FREQ_MAX_HZ)
        {
            trackedEnd = HEART_RATE_GUIDE_FREQ_MAX_HZ;
        }
        if (trackedEnd > trackedStart)
        {
            trackedFreq = HeartRateDss_findPeakFrequency(scratch->heartSignal,
                                                         length,
                                                         ctx->sampleRateHz,
                                                         trackedStart,
                                                         trackedEnd,
                                                         (uint16_t)(2U * length),
                                                         &trackedPeakMag);
            if (trackedPeakMag >= (HEART_RATE_TRACK_KEEP_RATIO * finePeakMag))
            {
                fineFreq      = trackedFreq;
                finePeakMag   = trackedPeakMag;
                trackSelected = 1U;
            }
        }
        candidateFreq    = fineFreq;
        candidatePeakMag = finePeakMag;

        if (fabsf(candidateFreq - ctx->trackedHeartRateHz) > HEART_RATE_SWITCH_GUARD_HZ)
        {
            if ((ctx->pendingSwitchCount == 0U) ||
                (fabsf(candidateFreq - ctx->pendingSwitchHeartRateHz) > HEART_RATE_SWITCH_CONFIRM_TOL_HZ))
            {
                ctx->pendingSwitchHeartRateHz = candidateFreq;
                ctx->pendingSwitchCount       = 1U;
            }
            else if (ctx->pendingSwitchCount < 0xFFFFU)
            {
                ctx->pendingSwitchCount++;
            }

            if (ctx->pendingSwitchCount < HEART_RATE_SWITCH_CONFIRM_COUNT)
            {
                fineFreq    = ctx->trackedHeartRateHz;
                finePeakMag = (trackedPeakMag > 0.0f) ? trackedPeakMag : candidatePeakMag;
            }
            else
            {
                ctx->pendingSwitchCount       = 0U;
                ctx->pendingSwitchHeartRateHz = candidateFreq;
            }
        }
        else
        {
            ctx->pendingSwitchCount       = 0U;
            ctx->pendingSwitchHeartRateHz = candidateFreq;
        }

        if (fineFreq > (ctx->trackedHeartRateHz + HEART_RATE_MAX_STEP_HZ))
        {
            fineFreq    = ctx->trackedHeartRateHz + HEART_RATE_MAX_STEP_HZ;
            stepLimited = 1U;
        }
        else if (fineFreq < (ctx->trackedHeartRateHz - HEART_RATE_MAX_STEP_HZ))
        {
            fineFreq    = ctx->trackedHeartRateHz - HEART_RATE_MAX_STEP_HZ;
            stepLimited = 1U;
        }
    }

    signalPower = 0.0f;
    for (sampleIdx = 0U; sampleIdx < length; sampleIdx++)
    {
        signalPower += scratch->heartSignal[sampleIdx] * scratch->heartSignal[sampleIdx];
    }
    signalPower /= (float)length;

    ctx->output.heartRateHz  = fineFreq;
    ctx->output.heartRateBpm = fineFreq * 60.0f;
    ctx->output.confidence   = finePeakMag / (signalPower + 1.0e-3f);
    ctx->output.valid        = (uint16_t)((ctx->output.heartRateBpm >= HEART_RATE_MIN_BPM) &&
                                          (ctx->output.heartRateBpm <= HEART_RATE_MAX_BPM));
    if (ctx->output.valid != 0U)
    {
        ctx->trackedHeartRateHz    = fineFreq;
        ctx->trackedHeartRateValid = 1U;
    }

    ctx->debugOutput.guideFreq                = guideFreq;
    ctx->debugOutput.vmeGuideFreq             = vmeGuideFreq;
    ctx->debugOutput.coarseFreq               = coarseFreq;
    ctx->debugOutput.runnerUpFreq             = runnerUpFreq;
    ctx->debugOutput.fineFreq                 = fineFreq;
    ctx->debugOutput.trackedFreq              = trackedFreq;
    ctx->debugOutput.coarsePeakMag            = coarsePeakMag;
    ctx->debugOutput.runnerUpPeakMag          = runnerUpPeakMag;
    ctx->debugOutput.finePeakMag              = finePeakMag;
    ctx->debugOutput.trackedPeakMag           = trackedPeakMag;
    ctx->debugOutput.signalPower              = signalPower;
    ctx->debugOutput.competitionRatio         = (coarsePeakMag > 0.0f) ? (runnerUpPeakMag / coarsePeakMag) : 0.0f;
    ctx->debugOutput.guideVmeGapHz            = fabsf(guideFreq - vmeGuideFreq);
    ctx->debugOutput.coarseFineGapHz          = fabsf(coarseFreq - fineFreq);
    ctx->debugOutput.trackedFineGapHz         = fabsf(trackedFreq - fineFreq);
    ctx->debugOutput.vmeLastRelErr            = vmeLastRelErr;
    ctx->debugOutput.estimateSeq              = ++(*estimateSeq);
    ctx->debugOutput.interFrameProcTimeUsec   = 0U;
    ctx->debugOutput.interFrameProcMarginUsec = 0U;
    ctx->debugOutput.txWriteTimeUsec          = 0U;
    ctx->debugOutput.txOverwriteCount         = 0U;
    ctx->debugOutput.vmeIterations            = vmeIterations;
    ctx->debugOutput.trackSelected            = trackSelected;
    ctx->debugOutput.stepLimited              = stepLimited;
    ctx->debugOutput.valid                    = ctx->output.valid;
}

static void HeartRateDss_processFrame(const HeartRateDssInfo *heartInfo,
                                      HeartRateDssCtx        *ctx,
                                      HeartRateDssScratch    *scratch,
                                      volatile uint32_t      *estimateSeq,
                                      HeartRateDssResult     *outResult)
{
    uint16_t numRangeBins;
    uint16_t rangeIdx;
    uint16_t searchMaxBin;
    uint16_t bestBin;
    uint16_t slowTimeSamplePushed;
    uint8_t  wasFilled;
    uint32_t deltaCycles;
    float    frameRateHz;
    float    frameDtSec;
    float    alpha;
    float    windowTimeSec;
    float    frameSamplesPerHeartSample;
    float    reVal;
    float    imVal;
    float    mtiRe;
    float    mtiIm;
    float    selectedRe;
    float    selectedIm;
    uint8_t  newSnapshotReady;

    if ((heartInfo == NULL) || (ctx == NULL) || (scratch == NULL) || (outResult == NULL))
    {
        return;
    }

    memset((void *)outResult, 0, sizeof(HeartRateDssResult));

    numRangeBins = heartInfo->numRangeBins;
    if (numRangeBins > HEART_RATE_MAX_RANGE_BINS)
    {
        numRangeBins = HEART_RATE_MAX_RANGE_BINS;
    }

    frameRateHz = ctx->frameRateHz;
    deltaCycles = heartInfo->frameStartTimeStamp - ctx->prevFrameStartTimeStamp;
    if ((ctx->prevFrameStartTimeStamp != 0U) && (deltaCycles != 0U))
    {
        frameRateHz = HEART_RATE_DSS_TIMESTAMP_HZ / (float)deltaCycles;
    }

    HeartRateDss_configureCtx(ctx, numRangeBins, heartInfo->rangeStep, frameRateHz);
    ctx->prevFrameStartTimeStamp = heartInfo->frameStartTimeStamp;

    if (ctx->frameRateHz > 0.0f)
    {
        frameDtSec = 1.0f / ctx->frameRateHz;
    }
    else if (ctx->sampleRateHz > 0.0f)
    {
        frameDtSec = 1.0f / ctx->sampleRateHz;
    }
    else
    {
        frameDtSec = 0.1f;
    }

    if ((ctx->sampleRateHz > 0.0f) && (ctx->windowLength > 0U))
    {
        windowTimeSec = (float)ctx->windowLength / ctx->sampleRateHz;
    }
    else
    {
        windowTimeSec = 0.0f;
    }

    if ((windowTimeSec > 0.0f) && (frameDtSec > 0.0f))
    {
        alpha = frameDtSec / windowTimeSec;
    }
    else if (ctx->windowLength > 0U)
    {
        alpha = 1.0f / (float)ctx->windowLength;
    }
    else
    {
        alpha = 1.0f;
    }
    if (alpha > 1.0f)
    {
        alpha = 1.0f;
    }

    bestBin              = HEART_RATE_RANGE_BIN_SKIP;
    selectedRe           = 0.0f;
    selectedIm           = 0.0f;
    slowTimeSamplePushed = 0U;
    wasFilled            = ctx->isFilled;
    newSnapshotReady     = 0U;
    searchMaxBin         = numRangeBins;

    if ((ctx->rangeStep > 0.0f) &&
        (((float)searchMaxBin * ctx->rangeStep) > 2.5f))
    {
        searchMaxBin = (uint16_t)(2.5f / ctx->rangeStep);
        if (searchMaxBin > numRangeBins)
        {
            searchMaxBin = numRangeBins;
        }
    }
    if (searchMaxBin <= HEART_RATE_RANGE_BIN_SKIP)
    {
        searchMaxBin = numRangeBins;
    }

    for (rangeIdx = 0U; rangeIdx < numRangeBins; rangeIdx++)
    {
        reVal = (float)heartInfo->rangeProfileRe[rangeIdx];
        imVal = (float)heartInfo->rangeProfileIm[rangeIdx];

        mtiRe = reVal - ctx->rangeMeanRe[rangeIdx];
        mtiIm = imVal - ctx->rangeMeanIm[rangeIdx];

        ctx->rangeMeanRe[rangeIdx] += alpha * mtiRe;
        ctx->rangeMeanIm[rangeIdx] += alpha * mtiIm;
        ctx->energyAccum[rangeIdx] += alpha * (HeartRateDss_magSq(mtiRe, mtiIm) - ctx->energyAccum[rangeIdx]);

        if ((rangeIdx >= HEART_RATE_RANGE_BIN_SKIP) &&
            (rangeIdx < searchMaxBin) &&
            ((bestBin == HEART_RATE_RANGE_BIN_SKIP) ||
             (ctx->energyAccum[rangeIdx] > ctx->energyAccum[bestBin])))
        {
            bestBin    = rangeIdx;
            selectedRe = mtiRe;
            selectedIm = mtiIm;
        }
    }

    if ((ctx->selectedRangeBin != 0xFFFFU) &&
        (bestBin != ctx->selectedRangeBin) &&
        (ctx->energyAccum[bestBin] < (1.10f * ctx->energyAccum[ctx->selectedRangeBin])))
    {
        bestBin    = ctx->selectedRangeBin;
        selectedRe = (float)heartInfo->rangeProfileRe[bestBin] - ctx->rangeMeanRe[bestBin];
        selectedIm = (float)heartInfo->rangeProfileIm[bestBin] - ctx->rangeMeanIm[bestBin];
    }

    if (ctx->selectedRangeBin != bestBin)
    {
        ctx->selectedRangeBin         = bestBin;
        ctx->sampleCount              = 0U;
        ctx->nextIndex                = 0U;
        ctx->slowTimeAccumCount       = 0U;
        ctx->samplesSinceEstimate     = 0U;
        ctx->isFilled                 = 0U;
        ctx->slowTimeAccumRe          = 0.0f;
        ctx->slowTimeAccumIm          = 0.0f;
        ctx->trackedHeartRateValid    = 0U;
        ctx->pendingSwitchCount       = 0U;
        ctx->pendingSwitchHeartRateHz = 0.0f;
        HeartRateDss_clearEstimate(ctx);
        newSnapshotReady              = 1U;
    }

    if (ctx->selectedRangeBin < numRangeBins)
    {
        frameSamplesPerHeartSample = 1.0f;
        if ((ctx->sampleRateHz > 0.0f) && (ctx->frameRateHz > ctx->sampleRateHz))
        {
            frameSamplesPerHeartSample = ctx->frameRateHz / ctx->sampleRateHz;
        }

        ctx->slowTimeAccumRe += selectedRe;
        ctx->slowTimeAccumIm += selectedIm;
        ctx->slowTimeAccumCount++;
        if ((ctx->slowTimeAccumCount >= (uint16_t)(frameSamplesPerHeartSample + 0.5f)) ||
            (frameSamplesPerHeartSample <= 1.0f))
        {
            HeartRateDss_pushSlowTimeSample(ctx,
                                            ctx->slowTimeAccumRe / (float)ctx->slowTimeAccumCount,
                                            ctx->slowTimeAccumIm / (float)ctx->slowTimeAccumCount);
            slowTimeSamplePushed    = 1U;
            ctx->slowTimeAccumCount = 0U;
            ctx->slowTimeAccumRe    = 0.0f;
            ctx->slowTimeAccumIm    = 0.0f;
        }
    }

    ctx->output.selectedRangeBin = ctx->selectedRangeBin;
    ctx->output.sampleRateHz     = ctx->sampleRateHz;
    ctx->output.windowLength     = ctx->windowLength;
    if (ctx->selectedRangeBin < numRangeBins)
    {
        ctx->output.rangeMeters = ((float)ctx->selectedRangeBin) * ctx->rangeStep;
    }
    else
    {
        ctx->output.rangeMeters = 0.0f;
    }

    if (slowTimeSamplePushed != 0U)
    {
        ctx->samplesSinceEstimate++;
        if ((ctx->isFilled == 0U) && (ctx->samplesSinceEstimate >= ctx->estimateStrideSamples))
        {
            HeartRateDss_clearEstimate(ctx);
            ctx->samplesSinceEstimate = 0U;
            newSnapshotReady          = 1U;
        }
        else if (((wasFilled == 0U) && (ctx->isFilled != 0U)) ||
                 ((ctx->isFilled != 0U) && (ctx->samplesSinceEstimate >= ctx->estimateStrideSamples)))
        {
            HeartRateDss_estimateForWindow(ctx, scratch, estimateSeq);
            ctx->samplesSinceEstimate = 0U;
            newSnapshotReady          = 1U;
        }
    }

    if (newSnapshotReady != 0U)
    {
        ctx->snapshotSeq++;
    }

    HeartRateDss_publishResult(ctx, outResult);
}

#endif /* HEART_RATE_DSS_PROC_H */
