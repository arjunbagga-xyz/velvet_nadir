// ── Canvas Animations — Ported from iconography_animations.html ──
// All drawing functions use dynamic colors from getActiveColors()

export class PRNG {
    constructor(seed) { this.seed = seed; }
    next() { this.seed = (this.seed * 9301 + 49297) % 233280; return this.seed / 233280; }
}

// ── Dynamic Color System ─────────────────────────────────────
let activeColors = {
    c1: { r: 0, g: 212, b: 255 },    // Cyan (#00d4ff)
    c2: { r: 255, g: 68, b: 170 },   // Magenta (#ff44aa)
    c3: { r: 68, g: 68, b: 68 }      // Grey (#444444)
};

// Force wipe old purple/blue theme from local storage
if (localStorage.getItem('themeColors')) {
    const cached = JSON.parse(localStorage.getItem('themeColors'));
    // If the cached primary is the old purple, wipe it
    if (cached.c1 && cached.c1.r === 139) {
        localStorage.removeItem('themeColors');
    }
}

export function getActiveColors() { return activeColors; }

export function getJumbledColors(profile = 0) {
    if (profile === 1) return { c1: activeColors.c2, c2: activeColors.c3, c3: activeColors.c1 }; // Context -> Device
    if (profile === 2) return { c1: activeColors.c3, c2: activeColors.c1, c3: activeColors.c2 }; // Agent -> Agent
    if (profile === 3) return { c1: { r: 100, g: 100, b: 100 }, c2: activeColors.c1, c3: activeColors.c3 }; // Boundary / Ext
    return activeColors; // Profile 0: Device -> Device (Standard)
}

export function setActiveColors(c1, c2, c3) {
    if (c1) activeColors.c1 = c1;
    if (c2) activeColors.c2 = c2;
    if (c3) activeColors.c3 = c3;
}

export function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) } : null;
}

// ── Math Utilities ───────────────────────────────────────────
export function lerpVal(a, b, t) { return a + (b - a) * t; }
export function lerp(a, b, t) { return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t }; }

export function splitBezier(t, p0, p1, p2, p3) {
    const q1 = lerp(p0, p1, t);
    const q2t = lerp(p1, p2, t);
    const q3t = lerp(p2, p3, t);
    const q2 = lerp(q1, q2t, t);
    const q3t2 = lerp(q2t, q3t, t);
    const q3 = lerp(q2, q3t2, t);
    return [p0, q1, q2, q3];
}

export function getBezierPoint(t, p0, p1, p2, p3) {
    const mt = 1 - t;
    return {
        x: mt * mt * mt * p0.x + 3 * mt * mt * t * p1.x + 3 * mt * t * t * p2.x + t * t * t * p3.x,
        y: mt * mt * mt * p0.y + 3 * mt * mt * t * p1.y + 3 * mt * t * t * p2.y + t * t * t * p3.y
    };
}

// ── drawEtherealBundle ─────────────────────────────────────
export function drawEtherealBundle(ctx, prng, opts) {
    const { startX, startY, cp1x, cp1y, cp2x, cp2y, endX, endY, count, spread, color1, color2, widthMultiplier = 1, timeOffset = 0, time = 0, progress = 1 } = opts;
    ctx.globalCompositeOperation = 'lighter';
    let threads = [];

    for (let i = 0; i < count; i++) {
        const n1 = (prng.next() - 0.5) * 2, n2 = (prng.next() - 0.5) * 2;
        const n3 = (prng.next() - 0.5) * 2, n4 = (prng.next() - 0.5) * 2;
        const timePhase = prng.next() * Math.PI * 2;
        const slowT = time * 0.0004;
        const wave1 = (Math.sin(time * 0.002 + i * 0.3 + timeOffset + timePhase) + Math.cos(slowT * 1.7 + i)) * 6;
        const wave2 = (Math.cos(time * 0.0025 + i * 0.2 + timeOffset - timePhase) + Math.sin(slowT * 1.3 - i)) * 6;
        let tipWanderX = Math.sin(time * 0.0015 + timePhase) * 6;
        let tipWanderY = Math.cos(time * 0.0017 - timePhase) * 6;

        let p0 = { x: startX + n1 * spread * 0.1, y: startY + n2 * spread * 0.1 };
        let p1 = { x: cp1x + n1 * spread + wave1, y: cp1y + n2 * spread + wave2 };
        let p2 = { x: cp2x + n3 * spread - wave1, y: cp2y + n4 * spread - wave2 };
        let p3 = { x: endX + n3 * spread * 0.3 + tipWanderX, y: endY + n4 * spread * 0.3 + tipWanderY };

        let lenT = 0.5 + Math.pow(prng.next(), 0.5) * 0.5;
        lenT *= Math.max(0, Math.min(1, progress));
        if (lenT <= 0.01) continue;

        let pts = splitBezier(lenT, p0, p1, p2, p3);
        threads.push({ pts, fullP3: p3 });
    }

    if (threads.length === 0) return;

    threads.sort((a, b) => {
        return Math.atan2(a.fullP3.y - startY, a.fullP3.x - startX) - Math.atan2(b.fullP3.y - startY, b.fullP3.x - startX);
    });

    for (let i = 0; i < threads.length - 1; i++) {
        let t1 = threads[i].pts, t2 = threads[i + 1].pts;
        ctx.beginPath();
        ctx.moveTo(t1[0].x, t1[0].y);
        ctx.bezierCurveTo(t1[1].x, t1[1].y, t1[2].x, t1[2].y, t1[3].x, t1[3].y);
        ctx.lineTo(t2[3].x, t2[3].y);
        ctx.bezierCurveTo(t2[2].x, t2[2].y, t2[1].x, t2[1].y, t2[0].x, t2[0].y);
        ctx.closePath();
        const grad = ctx.createLinearGradient(startX, startY, endX, endY);
        let webAlpha = 0.3 + prng.next() * 0.2;
        grad.addColorStop(0, color1.replace('ALPHA', webAlpha.toFixed(3)));
        grad.addColorStop(1, color2.replace('ALPHA', (webAlpha * 0.6).toFixed(3)));
        ctx.fillStyle = grad; ctx.fill();

        let linksToDraw = 1 + Math.floor(prng.next() * 3);
        for (let l = 0; l < linksToDraw; l++) {
            let linkT = 0.2 + prng.next() * 0.7;
            let pA = getBezierPoint(linkT, t1[0], t1[1], t1[2], t1[3]);
            let pB = getBezierPoint(linkT, t2[0], t2[1], t2[2], t2[3]);
            ctx.beginPath(); ctx.moveTo(pA.x, pA.y); ctx.lineTo(pB.x, pB.y);
            ctx.strokeStyle = color2.replace('ALPHA', '0.5');
            ctx.lineWidth = 0.25 * widthMultiplier; ctx.stroke();
        }
    }

    ctx.lineWidth = 0.75 * widthMultiplier;
    threads.forEach(tData => {
        let pts = tData.pts;
        ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
        ctx.bezierCurveTo(pts[1].x, pts[1].y, pts[2].x, pts[2].y, pts[3].x, pts[3].y);
        const grad = ctx.createLinearGradient(startX, startY, endX, endY);
        let threadAlpha = 0.5 + prng.next() * 0.5;
        grad.addColorStop(0, color1.replace('ALPHA', threadAlpha.toFixed(3)));
        grad.addColorStop(1, color2.replace('ALPHA', threadAlpha.toFixed(3)));
        ctx.strokeStyle = grad; ctx.stroke();
        ctx.beginPath(); ctx.arc(pts[3].x, pts[3].y, 1 * widthMultiplier, 0, Math.PI * 2);
        ctx.fillStyle = color2.replace('ALPHA', '0.8'); ctx.fill();
    });

    ctx.globalCompositeOperation = 'source-over';
}

// ── createNetworkNodes ─────────────────────────────────────
export function createNetworkNodes(prng, colors) {
    let numNodes = 6 + Math.floor(prng.next() * 4);
    let nodes = [];
    let cols = [colors.c1, colors.c2, colors.c3];
    for (let i = 0; i < numNodes; i++) {
        nodes.push({
            x: 20 + prng.next() * 130, y: -70 + prng.next() * 140,
            s: 1.5 + prng.next() * 2,
            col: cols[Math.floor(prng.next() * cols.length)],
            linkTo: [], connectToOrigin: false
        });
    }
    let numOriginLinks = 2 + Math.floor(prng.next() * 5);
    let indices = Array.from({ length: numNodes }, (_, i) => i);
    for (let i = 0; i < indices.length; i++) {
        let j = Math.floor(prng.next() * indices.length);
        [indices[i], indices[j]] = [indices[j], indices[i]];
    }
    for (let i = 0; i < numOriginLinks; i++) {
        if (indices[i] !== undefined) nodes[indices[i]].connectToOrigin = true;
    }
    for (let i = 0; i < numNodes; i++) {
        let links = Math.floor(prng.next() * 3);
        for (let l = 0; l < links; l++) {
            let target = i + 1 + Math.floor(prng.next() * (numNodes - i - 1));
            if (target < numNodes && !nodes[i].linkTo.includes(target)) nodes[i].linkTo.push(target);
        }
    }
    return nodes;
}

// ── drawNetworkNodes ───────────────────────────────────────
export function drawNetworkNodes(ctx, t, prngSeed, netOriginX, netOriginY, flipX, netEnergy, colors) {
    const prng = new PRNG(prngSeed);
    const nodes = createNetworkNodes(prng, colors);
    ctx.lineWidth = 0.5 + netEnergy;

    nodes.forEach((n, i) => {
        let nx = flipX ? -n.x : n.x;
        if (n.connectToOrigin) {
            ctx.beginPath(); ctx.moveTo(netOriginX, netOriginY);
            let cpX = netOriginX + nx * 0.5 + Math.sin(t * 0.001 + i) * 10;
            let cpY = netOriginY + n.y * 0.5 + Math.cos(t * 0.001 + i) * 10;
            ctx.quadraticCurveTo(cpX, cpY, netOriginX + nx, netOriginY + n.y);
            ctx.strokeStyle = `rgba(${n.col.r},${n.col.g},${n.col.b},${0.3 + netEnergy * 0.5})`;
            ctx.stroke();
        }
        n.linkTo.forEach(ti => {
            let target = nodes[ti], tnx = flipX ? -target.x : target.x;
            ctx.beginPath(); ctx.moveTo(netOriginX + nx, netOriginY + n.y);
            ctx.lineTo(netOriginX + tnx, netOriginY + target.y);
            ctx.strokeStyle = `rgba(100,100,200,${0.1 + netEnergy * 0.2})`; ctx.stroke();
        });
    });

    nodes.forEach(n => {
        let nx = flipX ? -n.x : n.x;
        ctx.beginPath(); ctx.arc(netOriginX + nx, netOriginY + n.y, n.s + netEnergy, 0, Math.PI * 2);
        ctx.fillStyle = `rgb(${n.col.r},${n.col.g},${n.col.b})`;
        ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = 5 + netEnergy * 15;
        ctx.fill(); ctx.shadowBlur = 0;
    });

    ctx.save(); ctx.translate(netOriginX, netOriginY);
    let spinDir = flipX ? -1 : 1;
    ctx.rotate(Math.PI / 4 + t * 0.0005 * spinDir);
    let coreSize = 6 + netEnergy * 4;
    ctx.fillStyle = '#E879F9'; ctx.shadowColor = '#E879F9';
    ctx.shadowBlur = 15 + netEnergy * 25;
    ctx.fillRect(-coreSize / 2, -coreSize / 2, coreSize, coreSize);
    ctx.shadowBlur = 0; ctx.restore();
}

// ── renderSilkPulseConnection (V6 two-way silk pulse) ──────
// Draws animated sine-wave strands between two arbitrary points
// with a travelling bright pulse. Fully dynamic — reads start/end each frame.
export function renderSilkPulseConnection(ctx, t, sx, sy, ex, ey, seed = 100, jumbleProfile = 0) {
    const colors = getJumbledColors(jumbleProfile);
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';


    const safeT = Math.max(0, t);
    const dx = ex - sx, dy = ey - sy;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < 1) { ctx.restore(); return; }

    // Angle from start to end
    const angle = Math.atan2(dy, dx);

    // Work in local space: 0..dist horizontal, then rotate
    ctx.translate(sx, sy);
    ctx.rotate(angle);

    const cycleDuration = 6000;
    let rawProgress = (safeT % cycleDuration) / (cycleDuration / 2);
    let isReversed = rawProgress >= 1;
    let progress = isReversed ? 2 - rawProgress : rawProgress;
    progress = Math.max(0, Math.min(1, progress));

    const strands = 6;
    const amplitude = Math.min(25, dist * 0.08);

    for (let i = 0; i < strands; i++) {
        ctx.beginPath();
        let phase = i * (Math.PI / 3) + seed * 0.1;
        let speed = 0.0015 + (i * 0.0002);

        for (let x = 0; x <= dist; x += 4) {
            let pct = x / dist;
            let envelope = Math.sin(pct * Math.PI);
            let wave1 = Math.sin(pct * 8 + safeT * speed + phase) * amplitude;
            let wave2 = Math.cos(pct * 5 - safeT * 0.001) * (amplitude * 0.6);
            let y = (wave1 + wave2) * envelope;
            if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }

        let grad = ctx.createLinearGradient(0, 0, dist, 0);
        let dimAlpha = 0.06;
        let cStr1 = `rgba(${colors.c1.r},${colors.c1.g},${colors.c1.b},${dimAlpha})`;
        let cStr2 = `rgba(${colors.c3.r},${colors.c3.g},${colors.c3.b},${dimAlpha})`;
        let brightAlpha = 0.7;
        let hStr1 = `rgba(${colors.c1.r},${colors.c1.g},${colors.c1.b},${brightAlpha})`;
        let hStr2 = `rgba(${colors.c3.r},${colors.c3.g},${colors.c3.b},${brightAlpha})`;

        let pulseWidth = 0.15;
        let startFade = Math.max(0, progress - pulseWidth);
        let endFade = Math.min(1, progress + pulseWidth);

        grad.addColorStop(0, cStr1);
        if (startFade > 0.001 && startFade < progress) grad.addColorStop(startFade, cStr1);
        grad.addColorStop(Math.max(0.001, Math.min(0.999, progress)), i % 2 === 0 ? hStr1 : hStr2);
        if (endFade < 0.999 && endFade > progress) grad.addColorStop(endFade, cStr2);
        grad.addColorStop(1, cStr2);

        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.5 + (i % 2);
        ctx.stroke();
    }

    ctx.restore();
    ctx.globalCompositeOperation = 'source-over';
}

// ── renderSilkPulseToAngle (for radial ops-mesh connections) ─
// Like renderSilkPulseConnection but takes polar coords from center
export function renderSilkPulseRadial(ctx, t, cx, cy, angle, radius, seed = 200) {
    const ex = cx + Math.cos(angle) * radius;
    const ey = cy + Math.sin(angle) * radius;
    renderSilkPulseConnection(ctx, t, cx, cy, ex, ey, seed);
}

// ── renderDormantSineConnection ─────────────────────────────
// A calm, multi-strand sine wave animation without travelling pulses.
// Used for "dormant" state connections (e.g. Context -> Device).
export function renderDormantSineConnection(ctx, t, sx, sy, ex, ey, seed = 300, jumbleProfile = 0) {
    const colors = getJumbledColors(jumbleProfile);
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';

    const safeT = Math.max(0, t);
    const dx = ex - sx, dy = ey - sy;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < 1) { ctx.restore(); return; }

    const angle = Math.atan2(dy, dx);
    ctx.translate(sx, sy);
    ctx.rotate(angle);

    const ribbonPoints = Math.floor(dist / 4); // Adaptive resolution
    const strands = 25;
    const prng = new PRNG(seed);

    for (let s = 0; s < strands; s++) {
        ctx.beginPath();
        let alpha = 0.04 + prng.next() * 0.05;
        let yOffsetBase = (prng.next() - 0.5) * 28; // Reduced from 40 (-30%)
        let phaseOff = prng.next() * Math.PI * 2;
        let freqOff = 0.8 + prng.next() * 0.4;

        for (let i = 0; i <= ribbonPoints; i++) {
            let pct = i / ribbonPoints;
            let x = pct * dist;
            let timeFactor = safeT * 0.001;

            // Replicates the specific sine wave pattern from V1/V7, but with amplitudes reduced by 30%
            let yWave = Math.sin(pct * Math.PI * 3 * freqOff + timeFactor + phaseOff) * 21 +
                Math.sin(pct * Math.PI * 5 - timeFactor * 0.5) * 10.5;

            let taper = Math.sin(pct * Math.PI); // Pinched at ends
            let y = yWave * taper + yOffsetBase * taper;

            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }

        const grad = ctx.createLinearGradient(0, 0, dist, 0);
        grad.addColorStop(0, `rgba(${colors.c1.r}, ${colors.c1.g}, ${colors.c1.b}, ${alpha})`);
        grad.addColorStop(0.5, `rgba(${colors.c2.r}, ${colors.c2.g}, ${colors.c2.b}, ${alpha})`);
        grad.addColorStop(1, `rgba(${colors.c3.r}, ${colors.c3.g}, ${colors.c3.b}, ${alpha})`);

        ctx.strokeStyle = grad;
        ctx.lineWidth = 2;
        ctx.stroke();
    }

    ctx.restore();
    ctx.globalCompositeOperation = 'source-over';
}

export function drawOrbitingDots(ctx, t, cx, cy, radius, seed) {
    const prng = new PRNG(seed);
    const numDots = 3 + Math.floor(prng.next() * 3); // 3 to 5 dots
    const colors = getActiveColors();
    const safeT = Math.max(0, t);

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';

    for (let i = 0; i < numDots; i++) {
        let baseAngle = (i / numDots) * Math.PI * 2 + prng.next();
        let speed = 0.0005 + prng.next() * 0.0005;
        let dir = prng.next() > 0.5 ? 1 : -1;
        let currentAngle = baseAngle + (safeT * speed * dir);

        // Slight orbital wobble
        let dist = radius + Math.sin(safeT * 0.002 + i) * (radius * 0.1);

        let x = cx + Math.cos(currentAngle) * dist;
        let y = cy + Math.sin(currentAngle) * dist;

        ctx.beginPath();
        ctx.arc(x, y, 2, 0, Math.PI * 2);

        let cObj = prng.next() > 0.5 ? colors.c1 : colors.c3;
        ctx.fillStyle = `rgba(${cObj.r}, ${cObj.g}, ${cObj.b}, 0.8)`;
        ctx.shadowColor = `rgb(${cObj.r}, ${cObj.g}, ${cObj.b})`;
        ctx.shadowBlur = 6;
        ctx.fill();

        // Faint connecting line to center
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(cx + Math.cos(currentAngle) * (radius * 0.7), cy + Math.sin(currentAngle) * (radius * 0.7));
        ctx.strokeStyle = `rgba(${cObj.r}, ${cObj.g}, ${cObj.b}, 0.15)`;
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    ctx.restore();
}

export function renderOrganicStreamV4(ctx, t, startX, startY, endX, endY, intensity = 1, seed = 888) {
    const prng = new PRNG(seed);
    const colors = getActiveColors();
    ctx.globalCompositeOperation = 'lighter';

    let safeT = Math.max(0, t);
    let c1 = `rgba(${colors.c1.r}, ${colors.c1.g}, ${colors.c1.b}, ALPHA)`;
    let c2 = `rgba(${colors.c2.r}, ${colors.c2.g}, ${colors.c2.b}, ALPHA)`;
    let c3 = `rgba(${colors.c3.r}, ${colors.c3.g}, ${colors.c3.b}, ALPHA)`;

    // Calculate dynamic anchor points for bezier based on start/end
    const dx = endX - startX;
    const dy = endY - startY;
    const dist = Math.sqrt(dx * dx + dy * dy);

    let drift1 = Math.sin(safeT * 0.0012) * (dist * 0.1), drift2 = Math.cos(safeT * 0.0015) * (dist * 0.1);

    // Create points spanning the distance
    let p0 = { x: startX, y: startY };
    let p1 = { x: startX + dx * 0.35 - dy * 0.2 + drift1, y: startY + dy * 0.35 + dx * 0.2 + drift1 };
    let p2 = { x: startX + dx * 0.65 + dy * 0.2 + drift2, y: startY + dy * 0.65 - dx * 0.2 + drift2 };
    let p3 = { x: endX, y: endY };

    ctx.save();
    ctx.globalAlpha = 0.15 * intensity;
    drawEtherealBundle(ctx, prng, {
        startX: p0.x, startY: p0.y, cp1x: p1.x, cp1y: p1.y, cp2x: p2.x, cp2y: p2.y, endX: p3.x, endY: p3.y,
        count: 2, spread: 15, color1: c1, color2: c3, timeOffset: 0, widthMultiplier: 0.5, progress: 1
    });
    ctx.restore();

    drawEtherealBundle(ctx, prng, {
        startX: p0.x, startY: p0.y, cp1x: p1.x, cp1y: p1.y, cp2x: p2.x, cp2y: p2.y, endX: p3.x, endY: p3.y,
        count: 4, spread: 45, color1: c1, color2: c3, timeOffset: safeT * 0.0005, widthMultiplier: 0.8, progress: intensity
    });

    drawEtherealBundle(ctx, prng, {
        startX: p0.x, startY: p0.y, cp1x: p1.x, cp1y: p1.y + 20, cp2x: p2.x, cp2y: p2.y - 20, endX: p3.x, endY: p3.y,
        count: 3, spread: 35, color1: c2, color2: c1, timeOffset: safeT * 0.0007 + 100, widthMultiplier: 0.8, progress: intensity
    });

    for (let i = 0; i < 40; i++) {
        let sparkP = prng.next();
        if (sparkP > intensity || intensity < 0.02) continue;

        let sparkPt = getBezierPoint(sparkP, p0, p1, p2, p3);
        let driftX = Math.sin(safeT * 0.001 + i) * 15;
        let driftY = Math.cos(safeT * 0.0015 + i) * 15 - ((safeT * 0.01 + i * 10) % 25);

        ctx.beginPath();
        ctx.arc(sparkPt.x + driftX, sparkPt.y + driftY, prng.next() * 1.5 + 0.5, 0, Math.PI * 2);
        let colObj = prng.next() > 0.5 ? colors.c1 : colors.c3;
        let alpha = (0.2 + prng.next() * 0.6) * Math.sin(sparkP * Math.PI) * intensity;
        ctx.fillStyle = `rgba(${colObj.r}, ${colObj.g}, ${colObj.b}, ${alpha})`; ctx.fill();
    }

    if (intensity > 0.01 && intensity < 0.99) {
        let headPt = getBezierPoint(intensity, p0, p1, p2, p3);
        ctx.beginPath(); ctx.arc(headPt.x, headPt.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#FFFFFF'; ctx.shadowColor = `rgb(${colors.c3.r}, ${colors.c3.g}, ${colors.c3.b})`; ctx.shadowBlur = 10; ctx.fill(); ctx.shadowBlur = 0;
    }

    ctx.beginPath(); ctx.arc(startX, startY, 6, 0, Math.PI * 2); ctx.fillStyle = `rgba(${colors.c1.r}, ${colors.c1.g}, ${colors.c1.b}, 0.8)`; ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = 15; ctx.fill();
    ctx.beginPath(); ctx.arc(startX, startY, 2, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.shadowBlur = 0;

    ctx.globalCompositeOperation = 'source-over';
}
