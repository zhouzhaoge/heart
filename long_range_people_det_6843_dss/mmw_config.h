/*
 * Copyright (C) 2024 Texas Instruments Incorporated
 *
 * All rights reserved not granted herein.
 * Limited License.
 *
 * Texas Instruments Incorporated grants a world-wide, royalty-free,
 * non-exclusive license under copyrights and patents it now or hereafter
 * owns or controls to make, have made, use, import, offer to sell and sell ("Utilize")
 * this software subject to the terms herein.  With respect to the foregoing patent
 * license, such license is granted  solely to the extent that any such patent is necessary
 * to Utilize the software alone.  The patent license shall not apply to any combinations which
 * include this software, other than combinations with devices manufactured by or for TI ("TI Devices").
 * No hardware patent is licensed hereunder.
 *
 * Redistributions must preserve existing copyright notices and reproduce this license (including the
 * above copyright notice and the disclaimer and (if applicable) source code license limitations below)
 * in the documentation and/or other materials provided with the distribution
 *
 * Redistribution and use in binary form, without modification, are permitted provided that the following
 * conditions are met:
 *
 *	* No reverse engineering, decompilation, or disassembly of this software is permitted with respect to any
 *     software provided in binary form.
 *	* any redistribution and use are licensed by TI for use only with TI Devices.
 *	* Nothing shall obligate TI to provide you with source code for the software licensed and provided to you in object code.
 *
 * If software source code is provided to you, modification and redistribution of the source code are permitted
 * provided that the following conditions are met:
 *
 *   * any redistribution and use of the source code, including any resulting derivative works, are licensed by
 *     TI for use only with TI Devices.
 *   * any redistribution and use of any object code compiled from the source code and any resulting derivative
 *     works, are licensed by TI for use only with TI Devices.
 *
 * Neither the name of Texas Instruments Incorporated nor the names of its suppliers may be used to endorse or
 * promote products derived from this software without specific prior written permission.
 *
 * DISCLAIMER.
 *
 * THIS SOFTWARE IS PROVIDED BY TI AND TI'S LICENSORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING,
 * BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
 * IN NO EVENT SHALL TI AND TI'S LICENSORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
 * OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

#ifndef MMW_CONFIG_H
#define MMW_CONFIG_H

/* MMWAVE library Include Files */
#include <ti/control/mmwave/mmwave.h>
#include <ti/common/sys_common.h>

/* Data path Include Files */
#include <dpc/objectdetectionandtracking/objdetrangehwa/objdetrangehwa.h>
#include <dpc/objectdetectionandtracking/objdetdsp/objectdetection.h>

#ifdef __cplusplus
extern "C"
{
#endif

    /**
     * @brief
     *  Millimeter Wave Demo Gui Monitor Selection
     *
     * @details
     *  The structure contains the selection for what information is placed to
     *  the output packet, and sent out to GUI. Unless otherwise specified,
     *  if the flag is set to 1, information
     *  is sent out. If the flag is set to 0, information is not sent out.
     *
     */
    typedef struct MmwDemo_GuiMonSel_t
    {
        /*! @brief   if 1: Send list of detected objects (see @ref DPIF_PointCloudCartesian) and
         *                 side info (@ref DPIF_PointCloudSideInfo).\n
         *           if 2: Send list of detected objects only (no side info)\n
         *           if 0: Don't send anything */
        uint8_t detectedObjects;

        /*! @brief   Send log magnitude range array  */
        uint8_t logMagRange;

        /*! @brief   Send noise floor profile */
        uint8_t noiseProfile;

        /*! @brief   Send complex range bins at zero doppler, all antenna symbols for range-azimuth heat map */
        uint8_t rangeAzimuthHeatMap;

        /*! @brief   Send complex range bins at zero doppler, (all antenna symbols), for range-azimuth heat map */
        uint8_t rangeDopplerHeatMap;

        /*! @brief   Send stats */
        uint8_t statsInfo;
    } MmwDemo_GuiMonSel;

    /**
     * @brief
     *  LVDS streaming configuration
     *
     * @details
     *  The structure is used to hold all the relevant configuration
     *  for the LVDS streaming.
     */
    typedef struct MmwDemo_LvdsStreamCfg_t
    {
        /**
         * @brief  HSI Header enabled/disabled flag. Only applicable for HW streaming.
         *         Will be ignored for SW streaming which will always have HSI header.
         */
        bool isHeaderEnabled;

        /*! HW STREAMING DISABLED */
#define MMW_DEMO_LVDS_STREAM_CFG_DATAFMT_DISABLED 0

        /*! ADC */
#define MMW_DEMO_LVDS_STREAM_CFG_DATAFMT_ADC 1

        /*! CP_ADC_CQ */
#define MMW_DEMO_LVDS_STREAM_CFG_DATAFMT_CP_ADC_CQ 4

        /*! HW streaming data format:
            0-HW STREAMING DISABLED
            1-ADC
            2-Reserved
            3-Reserved
            4-CP_ADC_CQ
        */
        uint8_t dataFmt;

        /**
         * @brief  SW enabled/disabled flag
         */
        bool isSwEnabled;
    } MmwDemo_LvdsStreamCfg;

    /**
     * @brief
     *  Millimeter Wave Demo Platform Configuration.
     *
     * @details
     *  The structure is used to hold all the relevant configuration for
     *  the Platform.
     */
    typedef struct MmwDemo_platformCfg_t
    {
        /*! @brief   GPIO index for sensor status */
        uint32_t SensorStatusGPIO;

        /*! @brief   CPU Clock Frequency. */
        uint32_t sysClockFrequency;

        /*! @brief   UART Logging Baud Rate. */
        uint32_t loggingBaudRate;

        /*! @brief   UART Command Baud Rate. */
        uint32_t commandBaudRate;
    } MmwDemo_platformCfg;

    /**
     * @brief
     *  Millimeter Wave Demo configuration
     *
     * @details
     *  The structure is used to hold all the relevant configuration
     *  which is used to execute the Millimeter Wave Demo.
     */
    typedef struct MmwDemo_Cfg_t
    {
        /*! @brief   mmWave Control Configuration. */
        MMWave_CtrlCfg ctrlCfg;

        /*! @brief   mmWave Open Configuration. */
        MMWave_OpenCfg openCfg;

        /*! @brief   Platform specific configuration. */
        MmwDemo_platformCfg platformCfg;
    } MmwDemo_Cfg;

    /**
     * @brief
     *  Data path DPC common configuraiton.
     *
     * @details
     *  The structure is used to hold all the relevant configuration for
     *  DPC common configuration.
     */
    typedef struct MmwDemo_DPC_ObjDet_CommonCfg_t
    {
        /*! @brief Flag indicating if new MeasureRxChannelBiasCfg configuration is
         *         pending issuance to DPC */
        uint8_t isMeasureRxChannelBiasCfgPending : 1;

        /*! @brief Flag indicating if new CompRxChannelBiasCfg configuration is
         *         pending issuance to DPC */
        uint8_t isCompRxChannelBiasCfgPending : 1;

        /*! @brief pre start common config */
        DPC_ObjectDetection_PreStartCommonCfg preStartCommonCfg;
    } MmwDemo_DPC_ObjDet_CommonCfg;

    /**
     * @brief
     *  Data path DPC dynamic configuraiton.
     *
     * @details
     *  The structure is used to hold all the relevant configuration for
     *  DPC dynamic configuration.
     */
    typedef struct MmwDemo_DPC_ObjDet_DynCfg_t
    {
        /*! @brief Flag indicating if new CalibDcRangeSigCfg configuration is
         *         pending issuance to DPC */
        uint16_t isCalibDcRangeSigCfg : 1;

        /*! @brief Flag indicating if new CfarCfgRange configuration is
         *         pending issuance to DPC */
        uint16_t isCfarCfgRangePending : 1;

        /*! @brief Flag indicating if new CfarCfgDoppler configuration is
         *         pending issuance to DPC */
        uint16_t isCfarCfgDopplerPending : 1;

        /*! @brief Flag indicating if new FovRange configuration is
         *         pending issuance to DPC */
        uint16_t isFovRangePending : 1;

        /*! @brief Flag indicating if new FovDoppler configuration is
         *         pending issuance to DPC */
        uint16_t isFovDopplerPending : 1;

        /*! @brief Flag indicating if new multiObjBeamFormingCfg configuration is
         *         pending issuance to DPC */
        uint16_t isMultiObjBeamFormingCfgPending : 1;

        /*! @brief Flag indicating if new PrepareRangeAzimuthHeatMap configuration is
         *         pending issuance to DPC */
        uint16_t isPrepareRangeAzimuthHeatMapPending : 1;

        /*! @brief Flag indicating if new fovAoaCfg configuration is
         *         pending issuance to DPC */
        uint16_t isFovAoaCfgPending : 1;

        /*! @brief Flag indicating if new StaticClutterRemovalCfg configuration is
         *         pending issuance to DPC */
        uint16_t isStaticClutterRemovalCfgPending : 1;

        /*! @brief Flag indicating if new extendedMaxVelocity configuration is
         *         pending issuance to DPC */
        uint16_t isExtMaxVelCfgPending : 1;

        /*! @brief dynamic config */
        DPC_ObjectDetectionRangeHWA_DynCfg r4fDynCfg;

        /*! @brief dynamic config */
        DPC_ObjectDetection_DynCfg dspDynCfg;
    } MmwDemo_DPC_ObjDet_DynCfg;

#ifdef __cplusplus
}
#endif

#endif /* MMW_CONFIG_H */
