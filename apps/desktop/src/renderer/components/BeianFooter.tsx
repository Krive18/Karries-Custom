const ICP_RECORD_NUMBER = "粤ICP备2025511993号-3";
const ICP_RECORD_URL = "https://beian.miit.gov.cn/";

export function BeianFooter() {
  return (
    <footer className="beian-footer">
      <a href={ICP_RECORD_URL} target="_blank" rel="noopener noreferrer">
        {ICP_RECORD_NUMBER}
      </a>
    </footer>
  );
}
