import { fireEvent, render, screen } from "@testing-library/react";

import { App } from "../App";


describe("KARRIES desktop workspace", () => {
  it("opens on the smart creation workspace with the expected navigation", () => {
    render(<App />);

    expect(screen.getByText("KARRIES")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "智能创作" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "定时发布" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "系统配置" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "素材智能解析" })).toBeInTheDocument();
    expect(screen.getByText("本地素材")).toBeInTheDocument();
    expect(screen.getByText("AI 解析结果")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI 智能解析" })).toBeInTheDocument();
  });

  it("accepts dropped local material files", () => {
    render(<App />);

    const uploadZone = screen.getByRole("button", { name: /拖入图片或视频到此处/ });
    const imageFile = new File(["image"], "look.png", { type: "image/png" });

    fireEvent.drop(uploadZone, {
      dataTransfer: {
        files: [imageFile]
      }
    });

    expect(screen.getByText("素材 1")).toBeInTheDocument();
    expect(screen.getByText("图片 1")).toBeInTheDocument();
  });

  it("switches to scheduled publishing tasks", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "定时发布" }));

    expect(screen.getByRole("heading", { name: "定时发布任务" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新建任务" })).toBeInTheDocument();
    expect(screen.getByText("已提交平台")).toBeInTheDocument();
  });

  it("switches to system settings", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "系统配置" }));

    expect(screen.getByRole("heading", { name: "系统配置" })).toBeInTheDocument();
    expect(screen.getByText("AI API KEY")).toBeInTheDocument();
    expect(screen.getByText("小红书账号管理")).toBeInTheDocument();
    expect(screen.getByText("运行环境检测")).toBeInTheDocument();
  });
});
