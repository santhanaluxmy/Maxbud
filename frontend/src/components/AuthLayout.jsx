
// import { Link } from "react-router-dom";
// import {
//   ArrowLeft,
//   ChartNoAxesCombined,
//   Target,
//   Sparkles,
//   CheckCircle2,
// } from "lucide-react";

// export default function AuthLayout({
//   children,
//   title = "Smarter Money Management",
// }) {
//   return (
//     <div className="relative min-h-screen overflow-hidden bg-[#FFF9ED] text-[#342116]">

//       {/* Soft background gradients */}
//       <div
//         className="pointer-events-none absolute inset-0"
//         style={{
//           background: `
//             radial-gradient(
//               circle at 90% 10%,
//               rgba(227,160,91,0.26),
//               transparent 38%
//             ),
//             radial-gradient(
//               circle at 5% 90%,
//               rgba(220,239,198,0.65),
//               transparent 40%
//             ),
//             #FFF9ED
//           `,
//         }}
//       />

//       <main className="relative mx-auto grid min-h-screen max-w-7xl items-center gap-8 px-4 py-7 lg:grid-cols-2 lg:px-8">

//         {/* LEFT BRANDING PANEL */}
//         <section className="relative hidden min-h-[680px] flex-col justify-between overflow-hidden rounded-[36px] border border-white/80 bg-linear-to-br from-[#FFF4DB] via-[#FFE3BD] to-[#DCEFC6] p-10 shadow-[0_20px_65px_rgba(166,118,86,0.12)] lg:flex">

//           <div className="absolute -right-20 -top-20 h-72 w-72 rounded-full bg-[#E3A05B]/25 blur-3xl" />

//           <div className="absolute -bottom-20 -left-12 h-64 w-64 rounded-full bg-[#DCEFC6]/80 blur-3xl" />

//           {/* Logo */}
//           <Link
//             to="/"
//             className="relative z-10 flex w-fit items-center gap-3"
//           >
//             <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-linear-to-br from-[#E8A247] to-[#BF682C] text-2xl font-black italic text-white shadow-md">
//               M
//             </span>

//             <span className="text-2xl font-extrabold tracking-tight">
//               Max<span className="text-[#B46D3D]">Bud</span>
//             </span>
//           </Link>

//           <div className="relative z-10 py-9">
//             <span className="inline-flex items-center gap-2 rounded-full border border-white/80 bg-white/65 px-4 py-2 text-xs font-bold tracking-wide text-[#A76535]">
//               <Sparkles size={16} />
//               YOUR SMART MONEY COMPANION
//             </span>

//             <h1 className="mt-8 max-w-md text-5xl font-extrabold leading-[1.12] tracking-tight">
//               Your Money.
//               <br />
//               Your Goals.
//               <br />
//               <span className="text-[#C87332]">
//                 Your MaxBud.
//               </span>
//             </h1>

//             <p className="mt-6 max-w-md text-lg leading-8 text-[#664A37]">
//               {title}
//             </p>

//             {/* Illustrative finance UI */}
//             <div className="mt-9 max-w-md rounded-[28px] border border-white/90 bg-white/70 p-6 shadow-[0_14px_40px_rgba(166,118,86,0.12)] backdrop-blur-xl">

//               <div className="flex items-center justify-between gap-3">
//                 <div>
//                   <p className="text-xs font-semibold uppercase tracking-wide text-[#A76535]">
//                     Monthly Budget
//                   </p>

//                   <p className="mt-2 text-2xl font-extrabold">
//                     Rs. 24,500
//                     <span className="ml-2 text-sm font-normal text-[#856956]">
//                       / 50,000
//                     </span>
//                   </p>
//                 </div>

//                 <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#FFE5BA] text-[#B87538]">
//                   <ChartNoAxesCombined size={25} />
//                 </span>
//               </div>

//               <div className="mt-5 h-3 overflow-hidden rounded-full bg-[#F4E7D5]">
//                 <div className="h-full w-[49%] rounded-full bg-linear-to-r from-[#E3A05B] to-[#C97332]" />
//               </div>

//               <p className="mt-2 text-xs text-[#795E4B]">
//                 49% of monthly budget used
//               </p>

//               <div className="mt-6 flex items-center gap-3 rounded-2xl bg-[#EAF4DF]/80 p-4">
//                 <Target size={23} className="text-[#729B52]" />

//                 <div>
//                   <p className="text-sm font-bold">
//                     Savings Goals
//                   </p>
//                   <p className="text-xs text-[#6C745B]">
//                     Plan, track and grow your savings
//                   </p>
//                 </div>

//                 <CheckCircle2
//                   size={20}
//                   className="ml-auto text-[#729B52]"
//                 />
//               </div>

//               <p className="mt-4 text-center text-[11px] text-[#9A806A]">
//                 Illustrative financial dashboard preview
//               </p>
//             </div>
//           </div>

//           <p className="relative z-10 text-sm font-medium text-[#755A46]">
//             Designed for smarter everyday budgeting.
//           </p>
//         </section>

//         {/* RIGHT FORM SECTION */}
//         <section className="mx-auto w-full max-w-[570px]">

//           {/* Mobile logo */}
//           <div className="mb-7 flex items-center justify-between lg:hidden">

//             <Link to="/" className="flex items-center gap-2">
//               <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-linear-to-br from-[#E8A247] to-[#BF682C] text-xl font-black italic text-white">
//                 M
//               </span>

//               <span className="text-2xl font-extrabold">
//                 Max<span className="text-[#B46D3D]">Bud</span>
//               </span>
//             </Link>

//             <Link
//               to="/"
//               className="flex items-center gap-1 text-sm font-semibold text-[#8C5A37]"
//             >
//               <ArrowLeft size={16} />
//               Home
//             </Link>
//           </div>

//           {/* Frosted glass form */}
//           <div className="rounded-[32px] border border-white/95 bg-white/80 p-6 shadow-[0_20px_65px_rgba(166,118,86,0.12)] backdrop-blur-xl sm:p-9">
//             {children}
//           </div>

//           <div className="mt-6 hidden justify-center lg:flex">
//             <Link
//               to="/"
//               className="inline-flex items-center gap-2 text-sm font-semibold text-[#8C5A37] transition hover:text-[#C87332]"
//             >
//               <ArrowLeft size={17} />
//               Back to Homepage
//             </Link>
//           </div>
//         </section>

//       </main>
//     </div>
//   );
// }
