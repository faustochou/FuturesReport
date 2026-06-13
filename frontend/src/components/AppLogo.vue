<template>
  <img
    :src="logoSrc"
    alt="Futures Reports Logo"
    :style="logoStyle"
  />
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'brand'
  }
})

const logoSrc = '/futures-reports-logo.svg'

const logoStyle = computed(() => {
  if (props.variant === 'hero') {
    return {
      display: 'block',
      width: '100%',
      height: 'auto'
    }
  }

  return {
    display: 'block',
    width: 'auto',
    height: '42px',
    maxWidth: '72px',
    objectFit: 'contain',
    flexShrink: '0'
  }
})
</script>
