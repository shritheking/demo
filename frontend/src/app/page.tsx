import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col items-center justify-center p-8">
      <div className="max-w-4xl w-full space-y-12 text-center">
        <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-600 bg-clip-text text-transparent">
          Infinity Trader
        </h1>
        <p className="text-xl md:text-2xl text-slate-300 max-w-2xl mx-auto">
          The ultimate platform for automated MT4/MT5 Expert Advisors and High-Performance VPS hosting.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-8">
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-xl hover:border-blue-500 transition-colors flex flex-col items-center">
            <h2 className="text-3xl font-bold mb-4">Expert Advisors</h2>
            <p className="text-slate-400 text-center mb-8">
              Get access to our highly profitable algorithmic trading bots. Licensed directly to your MT5 account.
            </p>
            <Link 
              href="/buy-ea"
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-8 rounded-full transition-transform hover:scale-105"
            >
              Browse EAs
            </Link>
          </div>

          <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-xl hover:border-indigo-500 transition-colors flex flex-col items-center">
            <h2 className="text-3xl font-bold mb-4">Trading VPS</h2>
            <p className="text-slate-400 text-center mb-8">
              Ultra-low latency VPS servers located near broker data centers for lightning-fast execution.
            </p>
            <Link 
              href="/buy-vps"
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-8 rounded-full transition-transform hover:scale-105"
            >
              View VPS Plans
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
