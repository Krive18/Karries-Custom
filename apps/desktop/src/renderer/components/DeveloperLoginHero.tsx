import { useEffect, useRef, useState } from "react";
import { Bot, ClipboardCheck, Film, ShieldCheck } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

import { useTypewriter } from "../hooks/useTypewriter";
import { BrandLogo } from "./BrandLogo";


const DEVELOPER_BACKGROUND_VIDEO =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260601_110537_3a579fa0-7bbc-4d94-9d25-0e816c7840f5.mp4";
const DEVELOPER_HEADLINE = "让可靠运行\n从这里开始";
const SCRAMBLE_CHARACTERS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ#@%&";

function ScrambleText({ text }: { text: string }) {
  const [visibleText, setVisibleText] = useState(text);

  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setVisibleText(text);
      return undefined;
    }

    let frame = 0;
    let animationFrame = 0;
    const animate = () => {
      frame += 1;
      const revealedLength = Math.floor(frame / 2);
      setVisibleText(
        Array.from(text, (character, index) => {
          if (character === " " || index < revealedLength) return character;
          return SCRAMBLE_CHARACTERS[
            Math.floor(Math.random() * SCRAMBLE_CHARACTERS.length)
          ];
        }).join("")
      );
      if (revealedLength < text.length) {
        animationFrame = window.requestAnimationFrame(animate);
      } else {
        setVisibleText(text);
      }
    };

    animationFrame = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(animationFrame);
  }, [text]);

  return <span aria-label={text}><span aria-hidden="true">{visibleText}</span></span>;
}

function useDesktopViewport() {
  const [isDesktop, setIsDesktop] = useState(
    () => window.matchMedia?.("(min-width: 1024px)").matches ?? false
  );

  useEffect(() => {
    const mediaQuery = window.matchMedia?.("(min-width: 1024px)");
    if (!mediaQuery) return undefined;
    const updateViewport = () => setIsDesktop(mediaQuery.matches);
    updateViewport();
    mediaQuery.addEventListener?.("change", updateViewport);
    return () => mediaQuery.removeEventListener?.("change", updateViewport);
  }, []);

  return isDesktop;
}

export function DeveloperLoginHero() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const previousXRef = useRef<number | null>(null);
  const pendingTimeRef = useRef<number | null>(null);
  const [videoAvailable, setVideoAvailable] = useState(true);
  const isDesktop = useDesktopViewport();
  const reduceMotion = useReducedMotion();
  const scrubEnabled = isDesktop && !reduceMotion;
  const { displayed, done } = useTypewriter(DEVELOPER_HEADLINE, 38, 600);
  const entrance = reduceMotion ? false : { opacity: 0, y: 20 };

  const applyPendingSeek = () => {
    const video = videoRef.current;
    if (!video || pendingTimeRef.current === null) return;
    const pendingTime = pendingTimeRef.current;
    pendingTimeRef.current = null;
    video.currentTime = pendingTime;
  };

  const handlePointerMove = (clientX: number) => {
    const video = videoRef.current;
    const previousX = previousXRef.current;
    previousXRef.current = clientX;
    if (!scrubEnabled || !video || previousX === null) return;
    if (!Number.isFinite(video.duration) || video.duration <= 0) return;

    const delta = clientX - previousX;
    const secondsPerPixel = video.duration / Math.max(window.innerWidth, 1024);
    const nextTime = Math.min(
      video.duration,
      Math.max(0, video.currentTime + delta * secondsPerPixel)
    );
    if (video.seeking) {
      pendingTimeRef.current = nextTime;
      return;
    }
    video.currentTime = nextTime;
  };

  const handleVideoReady = () => {
    const video = videoRef.current;
    if (!video) return;
    if (isDesktop || reduceMotion) {
      video.pause();
      return;
    }
    void video.play().catch(() => undefined);
  };

  return (
    <section
      className="developer-login-hero relative min-h-dvh overflow-hidden bg-neutral-950 text-neutral-100 font-sans antialiased"
      aria-label="点绘环球技术运营中心"
      data-scrub-enabled={String(scrubEnabled)}
      onMouseEnter={(event) => {
        previousXRef.current = scrubEnabled ? event.clientX : null;
      }}
      onMouseLeave={() => {
        previousXRef.current = null;
      }}
      onMouseMove={(event) => handlePointerMove(event.clientX)}
    >
      <div className="developer-login-media" aria-hidden="true">
        {videoAvailable ? (
          <video
            ref={videoRef}
            data-developer-login-video
            autoPlay={!isDesktop && !reduceMotion}
            muted
            loop
            playsInline
            preload="auto"
            aria-hidden="true"
            onLoadedMetadata={handleVideoReady}
            onSeeked={applyPendingSeek}
            onError={() => setVideoAvailable(false)}
          >
            <source src={DEVELOPER_BACKGROUND_VIDEO} type="video/mp4" />
          </video>
        ) : null}
        <div className="developer-login-media__wash" />
        <div className="developer-login-media__aurora" />
        <div className="developer-login-media__grid" />
        <div className="developer-login-media__scan" />
      </div>

      <header className="developer-login-brand">
        <BrandLogo inverse subtitle="点绘环球内部交付工作台" />
        <span className="developer-login-environment"><i /> INTERNAL ACCESS</span>
      </header>

      <div className="developer-login-copy">
        <motion.div
          initial={entrance}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <p><ScrambleText text="KARRIES / OPERATIONS CONSOLE" /></p>
          <h1 aria-label={DEVELOPER_HEADLINE.replace("\n", " ")}>
            <span aria-hidden="true">{displayed}</span>
            {!done ? <span className="animate-blink" aria-hidden="true">|</span> : null}
          </h1>
        </motion.div>

        <motion.div
          initial={entrance}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          <strong>统一处理真实任务、视频交付、AI 服务与操作审计。</strong>
          <div className="developer-login-capabilities" aria-label="工作台能力">
            <span><ClipboardCheck size={16} aria-hidden="true" />任务排查</span>
            <span><Film size={16} aria-hidden="true" />视频交付</span>
            <span><Bot size={16} aria-hidden="true" />AI Provider</span>
            <span><ShieldCheck size={16} aria-hidden="true" />审计追踪</span>
          </div>
        </motion.div>
      </div>

      <footer className="developer-login-footer">
        <span><i /> AUTH GATE ACTIVE</span>
        <span>移动设备自动播放 · 桌面横向移动浏览画面</span>
      </footer>
    </section>
  );
}
