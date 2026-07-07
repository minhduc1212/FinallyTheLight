<template>
  <div class="log-console-wrapper" style="margin-bottom: 24px;">
    <!-- Title / Actions bar -->
    <div style="display: flex; justify-content: space-between; align-items: center; background: #0c0d10; padding: 10px 16px; border-radius: 8px 8px 0 0; border-bottom: 1px solid #1f2026;">
      <span style="color: #a1a1aa; font-family: monospace; font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
        <span class="pulse-dot"></span> TERMINAL LOGS
      </span>
      <button 
        @click="emit('clear')" 
        style="background: none; border: none; color: #ef4444; font-size: 11px; font-family: monospace; cursor: pointer; text-decoration: none; font-weight: 600;"
        title="Xóa tất cả nhật ký hiện có"
      >
        Clear Console
      </button>
    </div>

    <!-- Terminal Output -->
    <div 
      ref="logContainer" 
      class="log-console" 
      style="max-height: 250px; border-radius: 0 0 8px 8px; border-top: none; padding: 12px 16px; background-color: #0c0d10;"
    >
      <div 
        v-for="(log, idx) in logs" 
        :key="idx" 
        v-html="formatLogLine(log)"
        class="log-row"
      >
      </div>
      
      <div v-if="logs.length === 0" style="color: #52525b; font-style: italic; font-size: 13px;">
        Đang đợi log sự kiện...
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  logs: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['clear'])

const logContainer = ref(null)

// Scroll to bottom helper
const scrollToBottom = async () => {
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

// Watch logs array to automatically scroll
watch(() => props.logs, scrollToBottom, { deep: true, immediate: true })

// Parse Rich/BBCode tags (e.g. [cyan]text[/cyan]) into HTML inline styles
function parseRichTags(text) {
  if (!text) return ''
  
  // Basic HTML escaping
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  
  const colors = {
    cyan: '#06b6d4',
    green: '#10b981',
    yellow: '#fbbf24',
    red: '#f87171',
    blue: '#60a5fa',
    magenta: '#e879f9',
    white: '#f4f4f5',
    slate: '#94a3b8'
  };

  let prevHtml;
  // Loop to parse nested BBCode tags
  do {
    prevHtml = html;
    html = html.replace(/\[([a-zA-Z\s_]+)\](.*?)\[\/\1\]/gi, (match, tag, content) => {
      const lowerTag = tag.toLowerCase();
      let style = '';
      const isBold = lowerTag.includes('bold');
      const isDim = lowerTag.includes('dim');
      
      let color = '';
      for (const [name, hex] of Object.entries(colors)) {
        if (lowerTag.includes(name)) {
          color = hex;
          break;
        }
      }
      
      if (color) style += `color: ${color};`;
      if (isBold) style += `font-weight: bold;`;
      if (isDim) style += `opacity: 0.6;`;
      
      return `<span style="${style}">${content}</span>`;
    });
  } while (html !== prevHtml);

  return html;
}

// Format the raw log line with sleek developer-styled tags
function formatLogLine(log) {
  if (!log) return ''
  const parsed = parseRichTags(log);
  
  // Decide terminal code tag
  let tag = '[LOG ]';
  let color = '#71717a'; // gray
  let isRunning = false;
  const upperLog = log.toUpperCase();
  
  if (upperLog.includes('LỖI') || upperLog.includes('FAILED') || upperLog.includes('ERROR')) {
    tag = '[FAIL]';
    color = '#f87171'; // red
  } else if (upperLog.includes('COMPLETED') || upperLog.includes('DONE') || upperLog.includes('SUCCESS') || upperLog.includes('FINISHED')) {
    tag = '[ OK ]';
    color = '#34d399'; // green
  } else if (upperLog.includes('TRANSLATING') || upperLog.includes('ATTEMPT') || upperLog.includes('TRY')) {
    tag = '[RUN ]';
    color = '#60a5fa'; // blue
    isRunning = true;
  } else if (upperLog.includes('STARTING') || upperLog.includes('INIT')) {
    tag = '[SYS ]';
    color = '#c084fc'; // purple
  } else if (upperLog.includes('CHECKPOINT')) {
    tag = '[WARN]';
    color = '#fbbf24'; // yellow
  }
  
  const tagClass = isRunning ? 'pulse-tag' : '';
  const tagSpan = `<span class="${tagClass}" style="color: ${color}; font-weight: bold; margin-right: 12px; font-family: monospace; flex-shrink: 0; user-select: none;">${tag}</span>`;
  
  return `<div style="display: flex; align-items: flex-start; margin-bottom: 6px; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; line-height: 1.5; color: #d4d4d8; word-break: break-all;">
    ${tagSpan}
    <span style="flex: 1;">${parsed}</span>
  </div>`;
}
</script>

<style scoped>
.pulse-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  background-color: #10b981;
  border-radius: 50%;
  box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
  animation: pulse 1.6s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
  }
  70% {
    transform: scale(1);
    box-shadow: 0 0 0 6px rgba(16, 185, 129, 0);
  }
  100% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
  }
}

.pulse-tag {
  animation: pulse-opacity 1.6s infinite;
}

@keyframes pulse-opacity {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}
</style>
