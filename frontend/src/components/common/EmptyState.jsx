import { ReceiptText } from "lucide-react";

export default function EmptyState({ icon: Icon = ReceiptText, title = "Nothing here yet", text = "Your data will appear here once you add it." }) {
  return <div className="db-empty"><Icon size={27}/><h4>{title}</h4><p>{text}</p></div>;
}
