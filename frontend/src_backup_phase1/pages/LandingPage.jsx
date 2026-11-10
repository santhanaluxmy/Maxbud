import { useState } from "react";
import { Link } from "react-router-dom";

import {
  ArrowRight,
  Check,
  ChevronDown,
  Landmark,
  PiggyBank,
  ReceiptText,
  ScanLine,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";

import Navbar from "../components/Navbar";

import logo from "../assets/images/maxbud-logo.png";
import financeHero from "../assets/images/maxbud hero.png";
import savingsHero from "../assets/images/maxbud2.png";

// ====================================
// FREE PLAN FEATURES
// ====================================

const freeBenefits = [
  "Register, Login & Personal Dashboard",
  "Manual Income & Expense Tracking",
  "Accounts Management",
  "Monthly Budgets & Basic Reports",
  "Basic Savings Goals",
  "Bill & Loan Reminders",
  "Limited AI Receipt Scanning (Planned)",
  "Basic AI Advice, Insights & Merchant Memory (Planned)",
];

// ====================================
// PREMIUM PLAN FEATURES
// ====================================

const premiumBenefits = [
  "Everything included in Free",
  "Expanded AI Receipt Scanning (Planned)",
  "Full Advanced Spending Insights (Planned)",
  "Full AI Money Advisor (Planned)",
  "AI Goal Planner & Spending Predictions (Planned)",
  "Household Management (Planned)",
  "Advanced Merchant Memory (Planned)",
];

// ====================================
// PRICING FEATURE COMPONENT
// ====================================

function PlanFeature({ children }) {
  return (
    <li className="plan-benefit">
      <span className="plan-benefit-check">
        <Check size={15} strokeWidth={2.8} />
      </span>

      <span>{children}</span>
    </li>
  );
}

// ====================================
// MAIN FEATURES
// ====================================

const features = [
  {
    label: "01 · ACCOUNTS",
    title: "All Your Accounts",
    description:
      "Cash, bank, savings and wallets in one clear view.",
    tone: "aqua",
  },
  {
    label: "02 · BUDGETS",
    title: "Budgets That Work",
    description:
      "Track category limits before you overspend.",
    tone: "pink",
  },
  {
    label: "03 · SMART SCANNING",
    title: "AI Receipt Scanner",
    description:
      "Scan, review and record expenses faster.",
    tone: "cream",
  },
  {
    label: "04 · GOALS",
    title: "Savings Goals",
    description:
      "Follow your goals one contribution at a time.",
    tone: "pink",
  },
  {
    label: "05 · INSIGHTS",
    title: "Spending Predictions",
    description:
      "Understand where your money could be heading.",
    tone: "aqua",
  },
  {
    label: "06 · HOUSEHOLDS",
    title: "Family Sharing",
    description:
      "Plan selected budgets and savings together.",
    tone: "cream",
  },
];

// ====================================
// FEATURE VISUALS
// ====================================

function FeatureVisual({ index }) {
  // Accounts
  if (index === 0) {
    return (
      <div className="visual-area accounts-visual">
        <div className="visual-account">
          <div className="mini-round">
            <Landmark size={21} />
          </div>

          <div>
            <small>Total Balance</small>
            <strong>LKR 285,400</strong>
          </div>

          <TrendingUp size={20} />
        </div>

        <div className="visual-account small-account">
          <Wallet size={17} />
          <span>Cash Wallet</span>
          <b>LKR 25,000</b>
        </div>

        <div className="visual-orb orb-one" />
      </div>
    );
  }

  // Budgets
  if (index === 1) {
    return (
      <div className="visual-area budget-visual">
        <div className="mini-chart">
          <div className="mini-chart-header">
            <span>Monthly Budget</span>
            <b>72%</b>
          </div>

          <div className="mini-chart-columns">
            {[38, 66, 50, 83, 59, 72, 46].map(
              (height, i) => (
                <div
                  key={i}
                  className="mini-column-track"
                >
                  <span
                    style={{
                      height: `${height}%`,
                    }}
                  />
                </div>
              )
            )}
          </div>

          <div className="chart-week">
            <span>M</span>
            <span>T</span>
            <span>W</span>
            <span>T</span>
            <span>F</span>
            <span>S</span>
            <span>S</span>
          </div>
        </div>
      </div>
    );
  }

  // AI Receipt Scanning
  if (index === 2) {
    return (
      <div className="visual-area receipt-visual">
        <div className="mini-receipt">
          <span className="receipt-top">
            <ReceiptText size={19} />
            Receipt
          </span>

          <span className="receipt-line" />
          <span className="receipt-line shorter" />
          <span className="receipt-line" />

          <div className="receipt-total">
            <small>Total</small>
            <b>LKR 4,250</b>
          </div>
        </div>

        <div className="scan-corner corner-one" />
        <div className="scan-corner corner-two" />

        <ScanLine
          className="scan-floating"
          size={37}
        />
      </div>
    );
  }

  // Savings Goals
  if (index === 3) {
    return (
      <div className="visual-area goals-visual">
        <img
          src={savingsHero}
          alt="MaxBud savings goals"
          className="goal-illustration"
        />

        <div className="goal-float">
          <span>Japan Trip</span>
          <strong>28% Saved</strong>

          <div className="mini-progress">
            <span />
          </div>
        </div>
      </div>
    );
  }

  // Spending Predictions
  if (index === 4) {
    return (
      <div className="visual-area predictions-visual">
        <div className="predictions-sheet">
          <div className="between">
            <span>Spending Insights</span>
            <TrendingUp size={18} />
          </div>

          <svg
            viewBox="0 0 270 105"
            role="img"
            aria-label="Illustrative spending trend"
          >
            <path
              d="M5 80 C35 72 36 40 65 53 S106 94 135 64 S174 25 203 38 S240 29 265 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="5"
              strokeLinecap="round"
            />

            <circle
              cx="265"
              cy="16"
              r="7"
              fill="currentColor"
            />
          </svg>

          <small>Estimated Future Trend</small>
        </div>
      </div>
    );
  }

  // Family Management
  return (
    <div className="visual-area family-visual">
      <div className="family-avatar family-one">
        <Users size={26} />
      </div>

      <div className="family-avatar family-two">
        A
      </div>

      <div className="family-avatar family-three">
        N
      </div>

      <div className="family-connection" />

      <span className="family-label">
        <Check size={15} />
        Shared Budget
      </span>
    </div>
  );
}

// ====================================
// FEATURE CARD
// ====================================

function FeatureCard({ feature, index }) {
  return (
    <article
      className={`showcase-card tone-${feature.tone}`}
      style={{
        "--order": index,
      }}
    >
      <div className="showcase-copy">
        <span className="showcase-label">
          {feature.label}
        </span>

        <h3>{feature.title}</h3>
        <p>{feature.description}</p>
      </div>

      <FeatureVisual index={index} />
    </article>
  );
}

// ====================================
// HOW IT WORKS
// ====================================

const steps = [
  [
    "01",
    "Create an Account",
    "Sign up and choose your preferences.",
  ],
  [
    "02",
    "Set Up Your Finances",
    "Add income, accounts, monthly budgets and goals.",
  ],
  [
    "03",
    "Track and Improve",
    "Review spending and savings progress.",
  ],
];

// ====================================
// FREQUENTLY ASKED QUESTIONS
// ====================================

const questions = [
  [
    "Is MaxBud free?",
    "Yes. Core personal budgeting is free. AI features have planned monthly usage limits.",
  ],
  [
    "Does MaxBud connect to my bank?",
    "No. MaxBud manually tracks accounts and transactions. It does not transfer actual money.",
  ],
  [
    "Can I scan bills?",
    "AI scanning is planned for a future release. Free users will have limited scans, while Premium users will have an expanded allowance.",
  ],
  [
    "Can I track savings goals?",
    "Yes. You can create savings goals and track contributions toward each target.",
  ],
  [
    "What is included in Premium?",
    "Premium is planned to include family budgeting, advanced AI insights, spending predictions and AI goal planning.",
  ],
];

// ====================================
// LANDING PAGE
// ====================================

export default function LandingPage() {
  const [openFaq, setOpenFaq] = useState(0);

  return (
    <div className="landing-page">
      <Navbar />

      <main>
        {/* =================================
            HERO SECTION
        ================================= */}

        <section
          className="landing-hero site-container"
          id="home"
        >
          <div className="landing-hero-copy">
            <h1>
              Take Control of Your Money with{" "}
              <span className="max-text">Max</span>
              <span className="bud-text">Bud</span>
            </h1>

            <p>
              Track spending, plan budgets, scan
              receipts and reach your savings goals —
              together with the people you love.
            </p>

            <div className="hero-buttons">
              <Link
                to="/register"
                className="max-btn aqua big"
              >
                Get Started
                <ArrowRight size={19} />
              </Link>

              <a
                href="#how-it-works"
                className="max-btn white big"
              >
                See How It Works
              </a>
            </div>
          </div>

          <div className="landing-hero-art">
            <img
              src={financeHero}
              alt="MaxBud finance illustration"
            />

            <div className="hero-floating hero-floating-top">
              <span>
                <TrendingUp size={15} />
                Saved This Month
              </span>

              <strong>LKR 42,500</strong>
            </div>

            <div className="hero-floating hero-floating-bottom">
              <span>
                <PiggyBank size={15} />
                Japan Trip
              </span>

              <strong>28% Complete</strong>
            </div>
          </div>
        </section>

        {/* =================================
            FEATURES SECTION
        ================================= */}

        <section
          className="landing-section site-container"
          id="features"
        >
          <div className="section-heading">
            <h2>
              Everything You Need to Budget Smarter
            </h2>

            <p>
              Beautiful, simple tools for everyday
              money management.
            </p>
          </div>

          <div className="showcase-grid">
            {features.map((feature, index) => (
              <FeatureCard
                key={feature.title}
                feature={feature}
                index={index}
              />
            ))}
          </div>

          <p className="section-footnote">
            Visual examples use illustrative data.
            AI and family features are part of the
            planned product.
          </p>
        </section>

        {/* =================================
            HOW IT WORKS SECTION
        ================================= */}

        <section
          className="landing-section site-container how-grid"
          id="how-it-works"
        >
          <div className="how-illustration">
            <img
              src={savingsHero}
              alt="MaxBud savings illustration"
            />
          </div>

          <div className="how-text">
            <h2>
              Start Your Financial Journey in Three
              Simple Steps
            </h2>

            <div className="steps-list">
              {steps.map(([number, title, description]) => (
                <div
                  className="how-step"
                  key={number}
                >
                  <span className="step-number">
                    {number}
                  </span>

                  <div>
                    <h3>{title}</h3>
                    <p>{description}</p>
                  </div>
                </div>
              ))}
            </div>

            <Link
              to="/register"
              className="max-btn aqua"
            >
              Start with MaxBud
              <ArrowRight size={17} />
            </Link>
          </div>
        </section>

        {/* =================================
            PRICING SECTION
        ================================= */}

        <section
          className="landing-section site-container"
          id="pricing"
        >
          <div className="section-heading pricing-heading">
            <h2>
              Choose the Right Plan for Your Money
            </h2>

            <p>
              Start free with everyday budgeting.
              Explore advanced AI-powered tools and
              family management with Premium.
            </p>
          </div>

          <div className="pricing-grid">
            {/* FREE PLAN */}

            <article className="plan-card glass-plan free-plan">
              <div className="plan-top">
                <div className="plan-symbol">
                  <Wallet size={23} />
                </div>

                <span className="plan-chip">
                  Personal Budgeting
                </span>
              </div>

              <h3>Free</h3>

              <div className="plan-price">
                LKR 0
                <small> / month</small>
              </div>

              <p>
                Everything you need to manage your
                everyday finances.
              </p>

              <ul className="plan-benefit-list">
                {freeBenefits.map((benefit) => (
                  <PlanFeature key={benefit}>
                    {benefit}
                  </PlanFeature>
                ))}
              </ul>

              <Link
                to="/register"
                className="max-btn aqua plan-action"
              >
                Get Started Free
                <ArrowRight size={17} />
              </Link>
            </article>

            {/* PREMIUM PLAN */}

            <article className="plan-card glass-plan premium-plan">
              <div className="plan-top">
                <div className="plan-symbol">
                  <Sparkles size={23} />
                </div>

                <span className="plan-chip premium-chip">
                  Coming Soon
                </span>
              </div>

              <h3>Premium</h3>

              <div className="plan-price">
                Price to Be Announced
              </div>

              <p>
                Unlock advanced financial insights,
                AI planning and family budgeting.
              </p>

              <ul className="plan-benefit-list">
                {premiumBenefits.map((benefit) => (
                  <PlanFeature key={benefit}>
                    {benefit}
                  </PlanFeature>
                ))}
              </ul>

              <Link
                to="/register"
                className="max-btn pink plan-action"
              >
                Explore MaxBud
                <ArrowRight size={17} />
              </Link>
            </article>
          </div>

          <p className="plans-disclaimer">
            This represents MaxBud's planned
            features. AI services, household
            management and Premium subscriptions
            may not yet be available in this build.
            Premium pricing has not been finalized.
            No payment is collected here.
          </p>
        </section>

        {/* =================================
            FAQ SECTION
        ================================= */}

        <section
          className="landing-section site-container"
          id="faq"
        >
          <div className="section-heading">
            <h2>
              Frequently Asked Questions
            </h2>
          </div>

          <div className="faq-list">
            {questions.map(
              ([question, answer], index) => (
                <div
                  className="faq-card"
                  key={question}
                >
                  <button
                    type="button"
                    onClick={() =>
                      setOpenFaq(
                        openFaq === index ? -1 : index
                      )
                    }
                    aria-expanded={
                      openFaq === index
                    }
                  >
                    {question}

                    <ChevronDown
                      size={20}
                      className={
                        openFaq === index
                          ? "rotate"
                          : ""
                      }
                    />
                  </button>

                  {openFaq === index && (
                    <p>{answer}</p>
                  )}
                </div>
              )
            )}
          </div>
        </section>
      </main>

      {/* =================================
          FOOTER
      ================================= */}

      <footer className="max-footer">
        <div className="site-container footer-content">
          <div>
            <img
              src={logo}
              alt="MaxBud"
            />

            <p>
              Smarter budgeting for everyday life.
            </p>
          </div>

          <p>
            © {new Date().getFullYear()} MaxBud ·
            Personal & Family Budgeting
          </p>

          <span>
            <ShieldCheck size={16} />
            No Bank Integration Required
          </span>
        </div>
      </footer>
    </div>
  );
}
