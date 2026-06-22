import React, { useState, useEffect } from 'react';
import { getOfficerComplaints } from '../../services/api';
import Charts from '../../components/admin/Charts';
import Loader from '../../components/Loader';
import { BarChart3 } from 'lucide-react';

const AdminAnalytics = () => {
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const data = await getOfficerComplaints();
      setComplaints(Array.isArray(data) ? data : data.items || []);
    } catch (error) {
      console.error('Failed to fetch analytics data', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="py-20"><Loader /></div>;
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-indigo-100 text-indigo-600 rounded-lg">
          <BarChart3 className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Analytics & Insights</h1>
          <p className="text-sm text-slate-500 mt-1">Deep dive into complaint data, demographics, and trends.</p>
        </div>
      </div>

      {/* Reusing the Charts component, but here it takes full focus */}
      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200">
        <Charts complaints={complaints} />
      </div>

      <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm space-y-6">
        <div>
          <h3 className="text-xl font-bold text-slate-800 tracking-tight">Export Reports & System Data</h3>
          <p className="text-slate-500 mt-1 text-sm">Download official PDF performance summaries or export the complaints database in CSV format.</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-4">
          <a 
            href={`${import.meta.env.VITE_API_URL?.replace('/api/v1', '') || 'http://127.0.0.1:8000'}/reports/pdf?type=monthly`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 py-3 px-6 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl shadow-md hover:shadow-lg transition-all text-sm hover:-translate-y-0.5"
          >
            Download PDF Report
          </a>
          <a 
            href={`${import.meta.env.VITE_API_URL?.replace('/api/v1', '') || 'http://127.0.0.1:8000'}/reports/csv`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 py-3 px-6 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 font-bold rounded-xl shadow-sm hover:shadow transition-all text-sm hover:-translate-y-0.5"
          >
            Export CSV Spreadsheet
          </a>
        </div>
      </div>
    </div>
  );
};

export default AdminAnalytics;
