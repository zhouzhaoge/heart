function [hr_czt] = vme_func_double_czt(binFilePath, K, my_filter, filter_order)
% vme_func_double_czt: 根据输入的雷达原始数据文件(bin)计算心率
% 输入: 
%       binFilePath - bin文件路径，例如 'E:\Graduation\database\papar_data\data_D\zlj_static_4\zlj_static_4_Raw_0.bin'
%       K - 对应VME等分解算法中的核心参数 (原默认值为10，替换代码中的 alpha 或其它参数)
%       my_filter - 滤波器参数，可传入 [b, a] 或通带频率 如 [1, 2]
%       filter_order - 滤波器阶数 (默认为3阶)
% 输出: hr_czt - 估计得到的心率值 (BPM)
% 算法流程：预处理 + MTI + 反正切提取相位 + 相位解缠 + VME提取信号 + Double-CZT心率估计

    %% 雷达参数设置
    numADCSamples = 256; % number of ADC samples per chirp
    numADCBits = 16;     % number of ADC bits per sample
    numTX = 1;           % 发射天线数
    numRX = 4;           % number of receivers
    numLanes = 2;        % do not change. number of lanes is always 2
    isReal = 0;          % set to 1 if real only data, 0 if complex data
    numframes = 3000;
    
    Fs = 6e6;            % ADC采样率
    c = 3*1e8;           % 光速
    ts = numADCSamples/Fs; % ADC采样时间
    slope = 70e12;       % 调频斜率
    B_valid = ts*slope;  % 有效带宽
    detaR = c/(2*B_valid); % 距离分辨率
    startFreq = 77e9;    % 起始频率
    lambda = c/startFreq; % 雷达信号波长
    virtualAntenna = numRX*numTX;
    fs = 50;             % 慢时间采样率 (帧率)

    %% 读取Bin文件（数据预处理）
    fid = fopen(binFilePath,'r');
    if fid == -1
        error(['无法打开文件，请检查路径和文件名：', binFilePath]);
    end
    adcDataRow = fread(fid, 'int16');
    if numADCBits ~= 16 
        l_max = 2^(numADCBits-1)-1;
        adcDataRow(adcDataRow > l_max) = adcDataRow(adcDataRow > l_max) - 2^numADCBits;
    end
    fclose(fid);

    process_num = numframes;
    fileSize = process_num*numADCSamples*numTX*numRX*2;   
    PRTnum = fix(fileSize/(numADCSamples*numRX));
    fileSize = PRTnum * numADCSamples*numRX;
    adcData = adcDataRow(1:fileSize);

    if isReal
        numChirps = fileSize/numADCSamples/numRX;
        LVDS = zeros(1, fileSize);
        LVDS = reshape(adcData, numADCSamples*numRX, numChirps);
        LVDS = LVDS.';
    else
        numChirps = fileSize/2/numADCSamples/numRX;
        LVDS = zeros(1, fileSize/2);
        % 向量化处理复数数据
        LVDS(1:2:end) = adcData(1:4:fileSize-1) + 1i * adcData(3:4:fileSize);
        LVDS(2:2:end) = adcData(2:4:fileSize) + 1i * adcData(4:4:fileSize);
        LVDS = reshape(LVDS, numADCSamples*numRX, numChirps);
        LVDS = LVDS.';
    end

    %% 重组数据
    temp = reshape(LVDS.', numADCSamples, numRX, numChirps);
    temp = permute(temp, [2, 1, 3]);
    adcData = reshape(temp, numRX, numChirps*numADCSamples);

    %% 距离FFT参数
    rangeRes = detaR; 
    rawData = reshape(adcData,virtualAntenna,numADCSamples, numChirps);

    channelNum = size(rawData,1);
    rangebinNum = size(rawData,2);
    frameNum = size(rawData,3);
    N = rangebinNum;

    adcData2 = adcData.';
    rawdata_radar = reshape(adcData2,rangebinNum,frameNum,channelNum);

    % 距离FFT
    range_win = hamming(rangebinNum);
    range_win_3d = repmat(range_win, [1, frameNum, channelNum]);
    temp = rawdata_radar .* range_win_3d;    
    range_profile = fft(temp, N, 1);         

    %% 静态滤波 (MTI)
    data_input = range_profile(:,:,1);
    clutter = mean(data_input, 2); 
    data_mti = data_input - clutter; 

    %% 距离门选择
    energy_profile = sum(abs(data_mti), 2); 
    min_valid_bin = 3; 
    energy_profile(1:min_valid_bin) = 0; 
    [~, target_bin] = max(energy_profile);

    %% 生命体征信号提取
    vital_signal_complex = squeeze(data_mti(target_bin, :)); 

    %% 相位解缠
    % --- 原本的 MATLAB unwrap 方法 (已注释) ---
    % vital_sign = angle(vital_signal_complex);
    % phi = unwrap(vital_sign); 
    % phase_raw = phi(:); 

    % --- 扩展相位导数法 (EDACM) ---
    I_comp = real(vital_signal_complex); 
    Q_comp = imag(vital_signal_complex);
    dI_ed = [0, diff(I_comp)]; 
    dQ_ed = [0, diff(Q_comp)];
    den_ed = I_comp.^2 + Q_comp.^2; 
    den_th = 0.5 * mean(den_ed); % 设立保护阈值防止分母过小
    den_ed(den_ed < den_th) = den_th;
    rho_ed = (I_comp .* dQ_ed - Q_comp .* dI_ed) ./ den_ed;
    rho_ed_filt = medfilt1(rho_ed, 3); % 小中值滤波滤除毛刺
    phi_edacm = cumsum(rho_ed_filt); 
    phase_raw = phi_edacm(:);
    
    Fs_slow = fs;
    n_slow = length(phase_raw);

    %% Stage 2: 心跳信号分离 (VME算法)
    % Part A: 引导频率估计
    if nargin < 4 || isempty(filter_order)
        filter_order = 3; 
    end
    
    if nargin < 3 || isempty(my_filter)
        hr_passband = [1, 2]; 
        [b, a] = butter(filter_order, hr_passband/(Fs_slow/2), 'bandpass');
    else
        % 获取传入的滤波器参数
        if iscell(my_filter)  % 传入了 {b, a}
            b = my_filter{1};
            a = my_filter{2};
        elseif length(my_filter) == 2 % 传入了通带例如 [1, 2]
            [b, a] = butter(filter_order, my_filter/(Fs_slow/2), 'bandpass');
        else
            error('滤波器参数格式不正确，请传入 [低频, 高频] 或 {b, a}');
        end
    end
    phase_filt = filtfilt(b, a, phase_raw);

    f_axis = (0:n_slow-1) * (Fs_slow / n_slow);
    fft_phase = fft(phase_filt);
    [~, idx] = max(abs(fft_phase(1:floor(n_slow/2))));
    f_guide = f_axis(idx); % 使用计算出的引导频率

    % Part B: VME 提取
    psi = [0; diff(phase_raw)]; 
    N_psi = length(psi);

    if nargin < 2
        alpha = 10;         
    else
        alpha = K; % 使用输入的 K 替代默认的 alpha 参数
    end
    tau = 0;            
    tol = 1e-6;           
    max_iter = 300;       

    freq_axis = 2 * pi * (0:N_psi-1) * (Fs_slow / N_psi); 
    freq_axis = freq_axis(:); 

    omega_i = 2 * pi * f_guide; 

    Psi_hat = fft(psi);
    d_hat = zeros(size(Psi_hat));
    lambda_hat = zeros(size(Psi_hat));

    for k = 1:max_iter
        d_hat_old = d_hat;
        
        dist_omega = (freq_axis - omega_i); 
        term_alpha = alpha^2 * (dist_omega).^4;
        
        numerator = Psi_hat + term_alpha .* d_hat_old + lambda_hat/2;
        denominator = (1 + term_alpha) .* (1 + 2 * alpha * (dist_omega).^2);
        d_hat = numerator ./ denominator;
        
        half_N = floor(N_psi/2);
        idx_pos = 1:half_N;
        d_power = abs(d_hat(idx_pos)).^2;
        
        numerator_omega = sum(freq_axis(idx_pos) .* d_power);
        denominator_omega = sum(d_power);
        
        if denominator_omega > 0
            omega_i = numerator_omega / denominator_omega;
        end
        
        lambda_hat = lambda_hat + tau * (d_hat + (Psi_hat - d_hat) - Psi_hat);
        
        err = norm(d_hat - d_hat_old, 2) / (norm(d_hat_old, 2) + eps);
        
        if err < tol
            break;
        end
    end

    s_heart = real(ifft(d_hat));
    s_heart = circshift(s_heart, [1, 0]); 

    %% Double-CZT 心率估计
    x_sig = s_heart;
    N_sig = length(x_sig);

    % --- 第一步：粗略搜索 ---
    f_min1 = 1;    
    f_max1 = 3.0;  
    M1 = N_sig;    
    df1 = (f_max1 - f_min1) / M1; 

    A1 = exp(1j * 2 * pi * f_min1 / Fs_slow);
    W1 = exp(-1j * 2 * pi * df1 / Fs_slow);
    Y_czt1 = czt(x_sig, M1, W1, A1);

    [~, locs_c1] = max(abs(Y_czt1)); 
    idx_N1 = locs_c1(1); 

    % --- 第二步：精细搜索 ---
    delta_idx = 2; 
    f_start2 = f_min1 + ((idx_N1 - 1) - delta_idx) * df1;
    f_end2   = f_min1 + ((idx_N1 - 1) + delta_idx) * df1;

    if f_start2 < 0.01; f_start2 = 0.01; end 

    M2 = N_sig; 
    df2 = (f_end2 - f_start2) / M2;
    M2_scalar = double(M2);
    df2_scalar = double(df2);
    Fs_scalar = double(Fs_slow);

    A2 = exp(1j * 2 * pi * double(f_start2) / Fs_scalar);
    W2 = exp(-1j * 2 * pi * df2_scalar / Fs_scalar);
    Y_czt2 = czt(x_sig, M2_scalar, W2, A2);

    [~, locs_c2] = max(abs(Y_czt2));
    idx_N2 = locs_c2(1); 

    f_est_czt = f_start2 + (idx_N2 - 1) * df2_scalar;
    hr_czt = f_est_czt * 60;
end
