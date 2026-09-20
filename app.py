//@version=5
indicator("SMC Pro Dashboard - Tandans + OB + FVG + Liquidity", overlay=true, max_boxes_count=500, max_labels_count=500, max_lines_count=500)

// ================= INPUTS =================
grpStruct  = "Estrikti Mache"
swingLen   = input.int(5, "Longè Swing", group=grpStruct, minval=2)
obLookback = input.int(10, "Max Bar pou chache OB", group=grpStruct, minval=3, maxval=30)
maxOB      = input.int(3, "Konbyen OB pou gade (chak sans)", group=grpStruct, minval=1, maxval=10)

grpFVG  = "Fair Value Gap"
showFVG = input.bool(true, "Montre FVG", group=grpFVG)
maxFVG  = input.int(3, "Konbyen FVG pou gade", group=grpFVG, minval=1, maxval=10)

grpLiq    = "Liquidity"
showLiq   = input.bool(true, "Montre Liquidity Pools", group=grpLiq)
liqTolPct = input.float(10, "Tolerans Liquidity (% ATR)", group=grpLiq, minval=1) / 100

grpHTF = "Tandans Big Timeframe"
htf1   = input.timeframe("60", "HTF 1", group=grpHTF)
htf2   = input.timeframe("D", "HTF 2", group=grpHTF)

// ATR - itilize pou tolerans ki mache sou NENPÒT pè (Gold, Forex, Crypto, elt.)
atrVal = ta.atr(14)

// Deklare tablo OB yo BADÈ (anvan yo itilize pi ba) - sa a te koze erè "Undeclared identifier"
var array<box> bullOBs = array.new<box>()
var array<box> bearOBs = array.new<box>()

// ================= SWING / ESTRIKTI MACHE =================
swingHigh = ta.pivothigh(high, swingLen, swingLen)
swingLow  = ta.pivotlow(low, swingLen, swingLen)

var float lastSH = na
var float lastSL = na
var float prevSH = na
var float prevSL = na

if not na(swingHigh)
    prevSH := lastSH
    lastSH := swingHigh
if not na(swingLow)
    prevSL := lastSL
    lastSL := swingLow

var string trend = "neutral"

brokeUp   = not na(lastSH) and ta.crossover(close, lastSH)
brokeDown = not na(lastSL) and ta.crossunder(close, lastSL)

isCHoCHUp   = brokeUp and trend != "bullish"
isBOSUp     = brokeUp and trend == "bullish"
isCHoCHDown = brokeDown and trend != "bearish"
isBOSDown   = brokeDown and trend == "bearish"

if brokeUp
    trend := "bullish"
    // Tandans lan vin bullish - efase tout OB bearish ki kont li kounye a
    if array.size(bearOBs) > 0
        for i = array.size(bearOBs) - 1 to 0
            box.delete(array.get(bearOBs, i))
        array.clear(bearOBs)

if brokeDown
    trend := "bearish"
    // Tandans lan vin bearish - efase tout OB bullish ki kont li kounye a
    if array.size(bullOBs) > 0
        for i = array.size(bullOBs) - 1 to 0
            box.delete(array.get(bullOBs, i))
        array.clear(bullOBs)

if isCHoCHUp
    label.new(bar_index, low, "CHoCH", style=label.style_label_up, color=color.new(color.lime, 0), textcolor=color.black, size=size.small, yloc=yloc.belowbar)
if isBOSUp
    label.new(bar_index, low, "BOS", style=label.style_label_up, color=color.new(color.green, 60), textcolor=color.white, size=size.tiny, yloc=yloc.belowbar)
if isCHoCHDown
    label.new(bar_index, high, "CHoCH", style=label.style_label_down, color=color.new(color.red, 0), textcolor=color.white, size=size.small, yloc=yloc.abovebar)
if isBOSDown
    label.new(bar_index, high, "BOS", style=label.style_label_down, color=color.new(color.maroon, 60), textcolor=color.white, size=size.tiny, yloc=yloc.abovebar)

// ================= ORDER BLOCK =================
findBullOB() =>
    float top = na
    float bot = na
    for i = 1 to obLookback
        if close[i] < open[i]
            top := math.max(open[i], close[i])
            bot := low[i]
            break
    [top, bot]

findBearOB() =>
    float top = na
    float bot = na
    for i = 1 to obLookback
        if close[i] > open[i]
            top := high[i]
            bot := math.min(open[i], close[i])
            break
    [top, bot]

if brokeUp
    [t, b] = findBullOB()
    if not na(t)
        newBullBox = box.new(bar_index - 1, t, bar_index + 30, b, border_color=color.green, bgcolor=color.new(color.green, 85))
        array.push(bullOBs, newBullBox)
        if array.size(bullOBs) > maxOB
            box.delete(array.shift(bullOBs))

if brokeDown
    [t2, b2] = findBearOB()
    if not na(t2)
        newBearBox = box.new(bar_index - 1, t2, bar_index + 30, b2, border_color=color.red, bgcolor=color.new(color.red, 85))
        array.push(bearOBs, newBearBox)
        if array.size(bearOBs) > maxOB
            box.delete(array.shift(bearOBs))

// Efase OB lè pri a travèse l nèt (mitigation)
if array.size(bullOBs) > 0
    for i = array.size(bullOBs) - 1 to 0
        bx = array.get(bullOBs, i)
        if close < box.get_bottom(bx)
            box.delete(bx)
            array.remove(bullOBs, i)
        else
            box.set_right(bx, bar_index + 30)

if array.size(bearOBs) > 0
    for i = array.size(bearOBs) - 1 to 0
        bx = array.get(bearOBs, i)
        if close > box.get_top(bx)
            box.delete(bx)
            array.remove(bearOBs, i)
        else
            box.set_right(bx, bar_index + 30)

// ================= FAIR VALUE GAP (FVG) =================
var array<box> bullFVGs = array.new<box>()
var array<box> bearFVGs = array.new<box>()

bullFVG = showFVG and trend == "bullish" and low > high[2]
bearFVG = showFVG and trend == "bearish" and high < low[2]

if bullFVG
    fvgBox = box.new(bar_index - 2, low, bar_index + 20, high[2], border_color=color.blue, bgcolor=color.new(color.blue, 88), border_style=line.style_dashed)
    array.push(bullFVGs, fvgBox)
    if array.size(bullFVGs) > maxFVG
        box.delete(array.shift(bullFVGs))

if bearFVG
    fvgBox2 = box.new(bar_index - 2, low[2], bar_index + 20, high, border_color=color.purple, bgcolor=color.new(color.purple, 88), border_style=line.style_dashed)
    array.push(bearFVGs, fvgBox2)
    if array.size(bearFVGs) > maxFVG
        box.delete(array.shift(bearFVGs))

// Efase FVG lè pri a ranpli gap la nèt
if array.size(bullFVGs) > 0
    for i = array.size(bullFVGs) - 1 to 0
        bx = array.get(bullFVGs, i)
        if close < box.get_bottom(bx)
            box.delete(bx)
            array.remove(bullFVGs, i)
        else
            box.set_right(bx, bar_index + 20)

if array.size(bearFVGs) > 0
    for i = array.size(bearFVGs) - 1 to 0
        bx = array.get(bearFVGs, i)
        if close > box.get_top(bx)
            box.delete(bx)
            array.remove(bearFVGs, i)
        else
            box.set_right(bx, bar_index + 20)

// ================= LIQUIDITY POOLS (Equal Highs/Lows) =================
var array<line> liqLines = array.new<line>()

if showLiq and not na(swingHigh) and not na(prevSH)
    tolH = atrVal * liqTolPct
    if math.abs(swingHigh - prevSH) <= tolH
        lnH = line.new(bar_index - swingLen - 5, swingHigh, bar_index + 10, swingHigh, color=color.orange, width=1, style=line.style_dotted)
        array.push(liqLines, lnH)
        if array.size(liqLines) > 6
            line.delete(array.shift(liqLines))

if showLiq and not na(swingLow) and not na(prevSL)
    tolL = atrVal * liqTolPct
    if math.abs(swingLow - prevSL) <= tolL
        lnL = line.new(bar_index - swingLen - 5, swingLow, bar_index + 10, swingLow, color=color.aqua, width=1, style=line.style_dotted)
        array.push(liqLines, lnL)
        if array.size(liqLines) > 6
            line.delete(array.shift(liqLines))

// ================= TANDANS BIG TIMEFRAME (HTF BIAS) =================
htf1Close = request.security(syminfo.tickerid, htf1, close, lookahead=barmerge.lookahead_off)
htf1EMA   = request.security(syminfo.tickerid, htf1, ta.ema(close, 50), lookahead=barmerge.lookahead_off)
htf2Close = request.security(syminfo.tickerid, htf2, close, lookahead=barmerge.lookahead_off)
htf2EMA   = request.security(syminfo.tickerid, htf2, ta.ema(close, 50), lookahead=barmerge.lookahead_off)

htf1Bias = htf1Close > htf1EMA ? "Bullish" : "Bearish"
htf2Bias = htf2Close > htf2EMA ? "Bullish" : "Bearish"

// ================= DASHBOARD =================
var table dash = table.new(position.top_right, 2, 5, bgcolor=color.new(color.black, 20), border_width=1, border_color=color.gray)

if barstate.islast
    table.cell(dash, 0, 0, "SMC Dashboard", text_color=color.white, bgcolor=color.new(color.blue, 40), text_size=size.small)
    table.cell(dash, 1, 0, syminfo.ticker, text_color=color.white, bgcolor=color.new(color.blue, 40), text_size=size.small)

    table.cell(dash, 0, 1, "Tandans (chart)", text_color=color.white, text_size=size.small)
    table.cell(dash, 1, 1, trend == "bullish" ? "Bullish ↑" : trend == "bearish" ? "Bearish ↓" : "Neutral", text_color=trend == "bullish" ? color.lime : trend == "bearish" ? color.red : color.gray, text_size=size.small)

    table.cell(dash, 0, 2, "Bias " + htf1, text_color=color.white, text_size=size.small)
    table.cell(dash, 1, 2, htf1Bias, text_color=htf1Bias == "Bullish" ? color.lime : color.red, text_size=size.small)

    table.cell(dash, 0, 3, "Bias " + htf2, text_color=color.white, text_size=size.small)
    table.cell(dash, 1, 3, htf2Bias, text_color=htf2Bias == "Bullish" ? color.lime : color.red, text_size=size.small)

    table.cell(dash, 0, 4, "OB Aktif (Buy/Sell)", text_color=color.white, text_size=size.small)
    table.cell(dash, 1, 4, str.tostring(array.size(bullOBs)) + " / " + str.tostring(array.size(bearOBs)), text_color=color.yellow, text_size=size.small)

// ================= ALÈT =================
alertcondition(isCHoCHUp, "CHoCH Bullish", "{{ticker}}: CHoCH bullish detekte - tandans chanje anlè")
alertcondition(isCHoCHDown, "CHoCH Bearish", "{{ticker}}: CHoCH bearish detekte - tandans chanje anba")
alertcondition(bullFVG, "Nouvo FVG Bullish", "{{ticker}}: Nouvo Fair Value Gap bullish fòme")
alertcondition(bearFVG, "Nouvo FVG Bearish", "{{ticker}}: Nouvo Fair Value Gap bearish fòme")
