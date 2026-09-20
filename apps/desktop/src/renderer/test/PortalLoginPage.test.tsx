import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, expect, it, vi } from "vitest";

import { Login } from "../pages/Login";


const originalMatchMedia = window.matchMedia;

function setViewportMatchMedia(isDesktop: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === "(min-width: 1024px)" ? isDesktop : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn()
    }))
  });
}

afterEach(() => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: originalMatchMedia
  });
});


it("presents the developer login as a real internal operations workspace", () => {
  setViewportMatchMedia(true);
  const { container } = render(
    <Login
      portal="developer"
      error=""
      isSubmitting={false}
      onSubmit={vi.fn()}
    />
  );

  expect(
    screen.getByRole("heading", { name: "让可靠运行 从这里开始" })
  ).toBeInTheDocument();
  expect(screen.getByText("任务排查")).toBeInTheDocument();
  expect(screen.getByText("视频交付")).toBeInTheDocument();
  expect(screen.getByText("AI Provider")).toBeInTheDocument();
  expect(screen.getByText("审计追踪")).toBeInTheDocument();

  const backgroundVideo = container.querySelector<HTMLVideoElement>(
    "video[data-developer-login-video]"
  );
  expect(backgroundVideo).not.toBeNull();
  expect(backgroundVideo).toHaveAttribute("loop");
  expect(backgroundVideo).toHaveAttribute("playsinline");
  expect(backgroundVideo).toHaveAttribute("preload", "auto");
  expect(backgroundVideo).toHaveAttribute("aria-hidden", "true");
  expect(backgroundVideo?.querySelector("source")).toHaveAttribute(
    "src",
    "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260601_110537_3a579fa0-7bbc-4d94-9d25-0e816c7840f5.mp4"
  );
  expect(backgroundVideo).not.toHaveAttribute("autoplay");

  Object.defineProperty(backgroundVideo, "duration", {
    configurable: true,
    value: 20
  });
  Object.defineProperty(backgroundVideo, "currentTime", {
    configurable: true,
    writable: true,
    value: 5
  });
  const hero = screen.getByLabelText("点绘环球技术运营中心");
  fireEvent.mouseEnter(hero, { clientX: 100 });
  fireEvent.mouseMove(hero, { clientX: 180 });
  expect(backgroundVideo?.currentTime).toBeGreaterThan(5);

  fireEvent.error(backgroundVideo as HTMLVideoElement);
  expect(
    container.querySelector("video[data-developer-login-video]")
  ).not.toBeInTheDocument();
  expect(container.querySelector(".developer-login-media__grid")).toBeInTheDocument();
});


it("autoplays the ambient video on mobile without enabling desktop scrubbing", () => {
  setViewportMatchMedia(false);
  const { container } = render(
    <Login
      portal="developer"
      error=""
      isSubmitting={false}
      onSubmit={vi.fn()}
    />
  );

  const backgroundVideo = container.querySelector<HTMLVideoElement>(
    "video[data-developer-login-video]"
  );
  expect(backgroundVideo).toHaveAttribute("autoplay");
  expect(screen.getByLabelText("点绘环球技术运营中心")).toHaveAttribute(
    "data-scrub-enabled",
    "false"
  );
});


it("keeps the developer login connected to the supplied authentication handler", async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(
    <Login
      portal="developer"
      error=""
      isSubmitting={false}
      onSubmit={onSubmit}
    />
  );

  fireEvent.change(screen.getByLabelText("登录账号"), {
    target: { value: " developer " }
  });
  fireEvent.change(screen.getByLabelText("登录密码"), {
    target: { value: "secure-password" }
  });
  fireEvent.click(screen.getByRole("button", { name: "进入工作空间" }));

  await waitFor(() => {
    expect(onSubmit).toHaveBeenCalledWith({
      login_name: "developer",
      password: "secure-password"
    });
  });
});


it("keeps saved browser credentials visually consistent with the fixed silver login form", () => {
  const stylesheet = readFileSync(
    resolve(process.cwd(), "src/renderer/styles/developer-silver-lab.css"),
    "utf8"
  );

  expect(stylesheet).toMatch(
    /\.lux-login-page--developer \.lux-login-field \.lux-login-input input:-webkit-autofill[^{]*\{[^}]*-webkit-text-fill-color:\s*#18232d[^}]*-webkit-box-shadow:\s*0 0 0 1000px #ffffff inset/s
  );
  expect(stylesheet).toMatch(
    /\.lux-login-page--developer \.lux-login-field\s*\{[^}]*display:\s*grid[^}]*border:\s*0[^}]*background:\s*transparent/s
  );
  expect(stylesheet).toMatch(
    /\.lux-login-page--developer \.lux-login-field \.lux-login-input\s*\{[^}]*grid-template-columns:\s*auto minmax\(0, 1fr\) auto[^}]*border:\s*1px solid #cbd7de[^}]*background:\s*#ffffff/s
  );
  expect(stylesheet).toMatch(
    /\.lux-login-page--developer \.lux-login-field \.lux-login-input:focus-within\s*\{[^}]*border-color:\s*#b7772d[^}]*box-shadow:\s*0 0 0 3px rgba\(183, 119, 45, 0\.12\)/s
  );
  expect(stylesheet).toMatch(
    /\.lux-login-page--developer \.lux-login-field \.lux-login-input input\s*\{[^}]*appearance:\s*none[^}]*background:\s*transparent\s*!important[^}]*box-shadow:\s*none/s
  );
  expect(stylesheet).toMatch(
    /\.lux-login-page--developer \.developer-login-copy h1\s*\{[^}]*color:\s*#14232d/s
  );
});
