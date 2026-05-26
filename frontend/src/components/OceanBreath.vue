<template>
  <div
    class="ocean-breath"
    :class="[theme, { 'reduced-motion': isReducedMotion }]"
    @mousemove="handleMouseMove"
    @touchmove="handleTouchMove"
  >
    <div class="static-gradient"></div>
    <canvas ref="canvasRef" class="ocean-canvas" v-show="!isReducedMotion"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

const props = defineProps({
  speed: { type: Number, default: 0.7 },
  intensity: { type: Number, default: 0.6 },
  theme: { type: String, default: 'day' },
  density: { type: Number, default: 1.0 }
})

const canvasRef = ref(null)
const isReducedMotion = ref(false)

let ctx = null
let animationFrameId
let particles = []
let time = 0
let scrollOffset = 0
let lastScrollY = 0
let scrollSpeed = 0
let batteryLevel = 1.0
let isBatterySaver = false

const lightSpot = { x: -100, y: -100, targetX: -100, targetY: -100 }

let lastFrameTime = 0
let fpsLimit = 60

const readColorToken = (token, fallback) => {
  if (typeof window === 'undefined') return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(token).trim()
  return value || fallback
}

class Particle {
  constructor(width, height) {
    this.x = Math.random() * width
    this.y = height + Math.random() * 50
    this.radius = Math.random() * 3 + 1
    this.speedY = Math.random() * 1 + 0.5
    this.maxLife = (Math.random() * 4 + 4) * 60
    this.life = this.maxLife
    this.opacity = Math.random() * 0.5 + 0.1
  }

  update(speedMultiplier, height, width, scrollSpeed) {
    this.y -= this.speedY * speedMultiplier
    this.life -= speedMultiplier
    const highlight = Math.min(scrollSpeed * 0.05, 0.5)
    this.opacity = Math.max(0, (this.life / this.maxLife) * (0.5 + highlight))

    if (this.life <= 0 || this.y < -50) {
      this.reset(height, width)
    }
  }

  reset(height, width) {
    this.x = Math.random() * width
    this.y = height + 10
    this.life = this.maxLife
    this.opacity = Math.random() * 0.5 + 0.1
  }

  draw(ctx, isNight) {
    ctx.beginPath()
    ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2)
    const color = isNight ? '255, 255, 255' : '255, 255, 255'
    ctx.fillStyle = `rgba(${color}, ${this.opacity})`
    ctx.fill()
  }
}

const checkReducedMotion = () => {
  const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  isReducedMotion.value = mediaQuery.matches
  mediaQuery.addEventListener('change', (e) => {
    isReducedMotion.value = e.matches
  })
}

const checkBattery = async () => {
  if ('getBattery' in navigator) {
    try {
      const battery = await navigator.getBattery()
      batteryLevel = battery.level
      isBatterySaver = !battery.charging && battery.level <= 0.2
      fpsLimit = isBatterySaver ? 30 : 60

      battery.addEventListener('levelchange', () => {
        batteryLevel = battery.level
        isBatterySaver = !battery.charging && battery.level <= 0.2
        fpsLimit = isBatterySaver ? 30 : 60
      })
    } catch (e) {
      // 忽略不支持的情况
    }
  }
}

const handleScroll = () => {
  const currentScrollY = window.scrollY
  scrollSpeed = Math.abs(currentScrollY - lastScrollY)
  scrollOffset = currentScrollY * 0.5
  lastScrollY = currentScrollY

  setTimeout(() => {
    if (scrollSpeed > 0) scrollSpeed *= 0.9
  }, 100)
}

const handleMouseMove = (e) => {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (rect) {
    lightSpot.targetX = e.clientX - rect.left
    lightSpot.targetY = e.clientY - rect.top
  }
}

const handleTouchMove = (e) => {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (rect && e.touches[0]) {
    lightSpot.targetX = e.touches[0].clientX - rect.left
    lightSpot.targetY = e.touches[0].clientY - rect.top
  }
}

const handleOrientation = (e) => {
  if (!canvasRef.value) return
  const { gamma, beta } = e
  if (gamma !== null && beta !== null) {
    const width = canvasRef.value.width
    const height = canvasRef.value.height
    lightSpot.targetX = width / 2 + gamma * 10
    lightSpot.targetY = height / 2 + (beta - 45) * 10
  }
}

const initParticles = (width, height) => {
  const particleCount = Math.floor(120 * props.density)
  particles = Array.from({ length: particleCount }, () => new Particle(width, height))
}

const drawWaves = (width, height, isNight) => {
  if (!ctx) return

  const amplitude = 20 * props.intensity
  const frequency = 0.6 / 100
  const phase = time * props.speed * 0.035 + scrollOffset * 0.01

  ctx.beginPath()

  const step = 20
  let prevX = 0
  let prevY = height / 2
    + Math.sin(phase) * amplitude
    + Math.sin(phase * 1.5) * amplitude * 0.5

  ctx.moveTo(prevX, prevY)

  for (let x = step; x <= width + step; x += step) {
    const y = height / 2
      + Math.sin(x * frequency + phase) * amplitude
      + Math.sin(x * frequency * 0.5 + phase * 1.5) * amplitude * 0.5

    const cpX = (prevX + x) / 2
    const cpY = (prevY + y) / 2

    ctx.quadraticCurveTo(prevX, prevY, cpX, cpY)

    prevX = x
    prevY = y
  }

  ctx.lineTo(prevX, prevY)

  ctx.lineWidth = 1.5
  const strokeColor = isNight
    ? readColorToken('--ocean-wave-stroke-night', 'rgba(216, 205, 239, 0.35)')
    : readColorToken('--ocean-wave-stroke-day', 'rgba(184, 173, 212, 0.5)')
  ctx.strokeStyle = strokeColor
  ctx.stroke()
}

const drawLightSpot = (width, height, isNight) => {
  if (!ctx) return

  lightSpot.x += (lightSpot.targetX - lightSpot.x) * 0.2
  lightSpot.y += (lightSpot.targetY - lightSpot.y) * 0.2

  const clampedY = Math.max(0, Math.min(lightSpot.y, height))

  const radius = 150 * props.intensity
  const gradient = ctx.createRadialGradient(lightSpot.x, clampedY, 0, lightSpot.x, clampedY, radius)

  if (isNight) {
    gradient.addColorStop(0, readColorToken('--ocean-light-night-start', 'rgba(216, 205, 239, 0.18)'))
    gradient.addColorStop(1, readColorToken('--ocean-light-night-end', 'rgba(216, 205, 239, 0)'))
  } else {
    gradient.addColorStop(0, readColorToken('--ocean-light-day-start', 'rgba(242, 180, 148, 0.2)'))
    gradient.addColorStop(1, readColorToken('--ocean-light-day-end', 'rgba(242, 180, 148, 0)'))
  }

  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, width, height)
}

const render = (timestamp) => {
  if (isReducedMotion.value) return

  const elapsed = timestamp - lastFrameTime
  const frameInterval = 1000 / fpsLimit

  if (elapsed > frameInterval) {
    lastFrameTime = timestamp - (elapsed % frameInterval)
    time++

    if (canvasRef.value && ctx) {
      const width = canvasRef.value.width
      const height = canvasRef.value.height

      ctx.clearRect(0, 0, width, height)

      const isNight = props.theme === 'night'

      drawWaves(width, height, isNight)

      particles.forEach(p => {
        p.update(props.speed, height, width, scrollSpeed)
        p.draw(ctx, isNight)
      })

      drawLightSpot(width, height, isNight)
    }
  }

  animationFrameId = requestAnimationFrame(render)
}

const resizeCanvas = () => {
  if (canvasRef.value) {
    const parent = canvasRef.value.parentElement
    if (parent) {
      const targetWidth = document.documentElement.clientWidth || window.innerWidth
      const targetHeight = parent.clientHeight

      const dpr = window.devicePixelRatio || 1
      canvasRef.value.width = targetWidth * dpr
      canvasRef.value.height = targetHeight * dpr
      if (ctx) ctx.scale(dpr, dpr)

      canvasRef.value.style.width = `${targetWidth}px`
      canvasRef.value.style.height = `${targetHeight}px`

      if (particles.length === 0) {
        initParticles(targetWidth, targetHeight)
      }
    }
  }
}

const debounce = (fn, delay) => {
  let timeoutId
  return (...args) => {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn(...args), delay)
  }
}

const handleResize = debounce(resizeCanvas, 200)

onMounted(() => {
  checkReducedMotion()
  checkBattery()

  if (canvasRef.value) {
    ctx = canvasRef.value.getContext('2d')
    resizeCanvas()
    window.addEventListener('resize', handleResize)
    window.addEventListener('scroll', handleScroll, { passive: true })

    if (window.DeviceOrientationEvent) {
      window.addEventListener('deviceorientation', handleOrientation)
    }

    if (!isReducedMotion.value) {
      animationFrameId = requestAnimationFrame(render)
    }
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('scroll', handleScroll)
  if (window.DeviceOrientationEvent) {
    window.removeEventListener('deviceorientation', handleOrientation)
  }
  cancelAnimationFrame(animationFrameId)
})

watch(() => props.density, () => {
  if (canvasRef.value) {
    initParticles(canvasRef.value.width, canvasRef.value.height)
  }
})

watch(isReducedMotion, (val) => {
  if (val) {
    cancelAnimationFrame(animationFrameId)
  } else {
    lastFrameTime = performance.now()
    animationFrameId = requestAnimationFrame(render)
  }
})
</script>

<style scoped>
.ocean-breath {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100vw;
  height: 50vh;
  z-index: 1;
  overflow: hidden;
  pointer-events: none;
  --ob-bg-color: var(--ocean-bg-day);
  transition: all 600ms ease-in-out;
}

.ocean-breath.night {
  --ob-bg-color: var(--ocean-bg-night);
}

.ocean-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.static-gradient {
  position: absolute;
  inset: 0;
  background: var(--ob-bg-color);
  opacity: 0;
  transition: opacity 600ms ease;
}

.ocean-breath.reduced-motion .static-gradient {
  opacity: 1;
}
</style>
