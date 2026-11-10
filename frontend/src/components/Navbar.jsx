
import { useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react";
import logo from "../assets/images/maxbud-logo.png";

const links = [
  ["Home", "#home"],
  ["Features", "#features"],
  ["How It Works", "#how-it-works"],
  ["Pricing", "#pricing"],
  ["FAQ", "#faq"],
];

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="max-navbar">
      <Link to="/" className="max-logo">
        <img src={logo} alt="MaxBud logo" />
      </Link>

      <nav className={`max-nav-links ${open ? "open" : ""}`}>
        {links.map(([label, hash]) => (
          <a
            key={label}
            href={hash}
            onClick={() => setOpen(false)}
          >
            {label}
          </a>
        ))}
      </nav>

      <div className="max-nav-actions">
        <Link to="/login" className="max-btn white">
          Login
        </Link>
        <Link to="/register" className="max-btn aqua">
          Get Started
        </Link>
      </div>

      <button
        type="button"
        className="max-menu-toggle"
        onClick={() => setOpen(!open)}
        aria-label="Toggle navigation"
        aria-expanded={open}
      >
        {open ? <X size={22} /> : <Menu size={22} />}
      </button>
    </header>
  );
}
