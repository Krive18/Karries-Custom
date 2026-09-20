import { useEffect, useState } from "react";


export function useTypewriter(text: string, speed = 38, startDelay = 600) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    setDisplayed("");
    setDone(false);

    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setDisplayed(text);
      setDone(true);
      return undefined;
    }

    const characters = Array.from(text);
    let characterIndex = 0;
    let intervalId: number | undefined;
    const timeoutId = window.setTimeout(() => {
      intervalId = window.setInterval(() => {
        characterIndex += 1;
        setDisplayed(characters.slice(0, characterIndex).join(""));
        if (characterIndex >= characters.length) {
          if (intervalId !== undefined) window.clearInterval(intervalId);
          setDone(true);
        }
      }, speed);
    }, startDelay);

    return () => {
      window.clearTimeout(timeoutId);
      if (intervalId !== undefined) window.clearInterval(intervalId);
    };
  }, [speed, startDelay, text]);

  return { displayed, done };
}
