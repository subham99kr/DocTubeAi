import PdfUploader from "./PdfUploader";

import UrlInput from "./UrlInput";

export default function ContextBar() {
  return (
    <div className="border-b border-[#30363d] bg-[#11141a] p-4 flex flex-col gap-5">
      <div>
        <h2 className="text-lg font-semibold mb-3">
          Add PDFs
        </h2>

        <PdfUploader />
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">
          Add YouTube Context
        </h2>

        <UrlInput />
      </div>
    </div>
  );
}