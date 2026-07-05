import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
interface WaveformProps {
  bars?: number;
  className?: string;
  barClassName?: string;
  minHeight?: number;
  maxHeight?: number;
  /** width of each bar in px */
  barWidth?: number;
  /** gap between bars in px */
  gap?: number;
}
/**
 * Animated equalizer / soundwave. Monochrome, framer-motion driven.
 * Each bar oscillates on a looping ease with a staggered delay so the
 * group reads like a live audio signal.
 *
 * Duplicated locally so the /internal surface has no cross-folder deps.
 */
export function Waveform({
  bars = 24,
  className = '',
  barClassName = 'bg-ink',
  minHeight = 6,
  maxHeight = 40,
  barWidth = 4,
  gap = 4
}: WaveformProps) {
  const peaks = useMemo(
    () =>
    Array.from(
      {
        length: bars
      },
      (_, i) => {
        const t = i / bars;
        const envelope =
        Math.abs(Math.sin(t * Math.PI)) * 0.6 +
        Math.abs(Math.sin(t * Math.PI * 4)) * 0.4;
        return minHeight + envelope * (maxHeight - minHeight);
      }
    ),
    [bars, minHeight, maxHeight]
  );
  return (
    <div
      className={`flex items-center justify-center ${className}`}
      style={{
        gap
      }}
      role="presentation"
      aria-hidden="true">
      
      {peaks.map((peak, i) =>
      <motion.span
        key={i}
        className={`rounded-full ${barClassName}`}
        style={{
          width: barWidth
        }}
        initial={{
          height: minHeight
        }}
        animate={{
          height: [minHeight, peak, minHeight * 1.4, peak * 0.7, minHeight]
        }}
        transition={{
          duration: 1.6 + i % 5 * 0.15,
          repeat: Infinity,
          ease: 'easeInOut',
          delay: i % 8 * 0.08
        }} />

      )}
    </div>);

}
