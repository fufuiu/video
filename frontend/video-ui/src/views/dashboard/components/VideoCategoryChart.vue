<template>
  <div class="chart-card">
    <div class="chart-header">
      <h3>视频分类分布</h3>
      <span class="chart-subtitle">南丁格尔玫瑰图</span>
    </div>
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as echarts from 'echarts';

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  }
});

const chartRef = ref(null);
let chartInstance = null;

// 克制的纯色色板，避免统计图出现模板化渐变
const colorPalette = [
  '#4f46e5',
  '#0ea5e9',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#14b8a6',
  '#64748b',
  '#ec4899',
  '#6366f1'
];

const initChart = () => {
  if (!chartRef.value) return;
  
  chartInstance = echarts.init(chartRef.value);
  
  // 转换数据为玫瑰图格式
  const chartData = props.data.map((item, index) => ({
    value: item.count,
    name: item.category,
    itemStyle: {
      color: colorPalette[index % colorPalette.length]
    }
  }));
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: {
        color: '#666',
        fontSize: 12
      },
      itemGap: 12,
      formatter: (name) => {
        const item = props.data.find(d => d.category === name);
        return `${name}  ${item ? item.count : 0}`;
      }
    },
    series: [
      {
        name: '视频分类',
        type: 'pie',
        radius: [30, 120],
        center: ['35%', '50%'],
        roseType: 'area',
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'outside',
          formatter: '{b}\n{d}%',
          fontSize: 11,
          color: '#666'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold'
          },
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        labelLine: {
          show: true,
          length: 15,
          length2: 10,
          smooth: true
        },
        data: chartData
      }
    ]
  };
  
  chartInstance.setOption(option);
};

const updateChart = () => {
  if (!chartInstance) return;
  
  const chartData = props.data.map((item, index) => ({
    value: item.count,
    name: item.category,
    itemStyle: {
      color: colorPalette[index % colorPalette.length]
    }
  }));
  
  chartInstance.setOption({
    legend: {
      formatter: (name) => {
        const item = props.data.find(d => d.category === name);
        return `${name}  ${item ? item.count : 0}`;
      }
    },
    series: [
      {
        data: chartData
      }
    ]
  });
};

const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize();
  }
};

onMounted(() => {
  initChart();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose();
  }
  window.removeEventListener('resize', handleResize);
});

watch(() => props.data, () => {
  updateChart();
}, { deep: true });
</script>

<style scoped>
.chart-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid #e5e7eb;
  transition: all 0.2s;
}

.chart-card:hover {
  border-color: #d1d5db;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.chart-header h3 {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}

.chart-subtitle {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.chart-container {
  width: 100%;
  height: 380px;
}
</style>
