import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { trackComplaint, updateComplaintStatus } from '../../services/api';
import StatusBadge from '../../components/StatusBadge';
import Loader from '../../components/Loader';
import { ArrowLeft, MapPin, Clock, User, CheckCircle, AlertTriangle, Paperclip, Save } from 'lucide-react';
import toast from 'react-hot-toast';

const ComplaintDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const [complaint, setComplaint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Update state
  const [newStatus, setNewStatus] = useState('');
  const [remarks, setRemarks] = useState('');
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    fetchComplaintDetail();
  }, [id]);

  const fetchComplaintDetail = async () => {
    try {
      setLoading(true);
      const data = await trackComplaint(id);
      setComplaint(data);
      setNewStatus(data.status || 'SUBMITTED');
    } catch (err) {
      setError('Failed to fetch complaint details.');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async () => {
    try {
      setUpdating(true);
      await updateComplaintStatus(id, newStatus);
      setComplaint({ ...complaint, status: newStatus });
      toast.success('Status updated successfully!');
    } catch (err) {
      toast.error('Failed to update status.');
    } finally {
      setUpdating(false);
    }
  };

  if (loading) return <div className="py-20"><Loader /></div>;
  
  if (error || !complaint) return (
    <div className="bg-rose-50 text-rose-600 p-6 rounded-xl border border-rose-100 text-center animate-fade-in">
      <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
      <h3 className="text-lg font-bold">Error</h3>
      <p>{error || 'Complaint not found.'}</p>
      <button onClick={() => navigate('/admin/complaints')} className="mt-4 px-4 py-2 bg-white text-rose-600 rounded-lg border border-rose-200 font-medium hover:bg-rose-50 transition-colors">
        Back to List
      </button>
    </div>
  );

  const getStepStatus = (step) => {
    const statusOrder = ['SUBMITTED', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED'];
    const current = statusOrder.indexOf(complaint.status?.toUpperCase());
    const target = statusOrder.indexOf(step);
    if (target <= current) return 'completed';
    if (target === current + 1) return 'current';
    return 'upcoming';
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between bg-white p-4 rounded-xl shadow-sm border border-slate-200">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate('/admin/complaints')}
            className="p-2 hover:bg-slate-100 rounded-lg text-slate-500 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-slate-800">Ticket: {complaint.ticket_id || id}</h1>
            <p className="text-sm text-slate-500">{complaint.title || complaint.category || 'Complaint Details'}</p>
          </div>
        </div>
        <StatusBadge status={complaint.status} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-6">
            <h2 className="text-lg font-bold text-slate-800 border-b border-slate-100 pb-2">Complaint Details</h2>
            
            <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
              {complaint.description || 'No description provided.'}
            </p>

            <div className="grid grid-cols-2 gap-4 pt-4">
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                <div className="text-xs font-semibold text-slate-400 uppercase mb-1 flex items-center gap-1"><MapPin className="w-3 h-3"/> District</div>
                <div className="font-medium text-slate-800">{complaint.district || 'N/A'}</div>
              </div>
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                <div className="text-xs font-semibold text-slate-400 uppercase mb-1 flex items-center gap-1"><User className="w-3 h-3"/> Citizen</div>
                <div className="font-medium text-slate-800">{complaint.citizen_name || 'Anonymous'}</div>
              </div>
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                <div className="text-xs font-semibold text-slate-400 uppercase mb-1 flex items-center gap-1"><Clock className="w-3 h-3"/> Submitted On</div>
                <div className="font-medium text-slate-800">{complaint.created_at ? new Date(complaint.created_at).toLocaleString() : 'N/A'}</div>
              </div>
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                <div className="text-xs font-semibold text-slate-400 uppercase mb-1 flex items-center gap-1"><AlertTriangle className="w-3 h-3"/> Priority</div>
                <div className="font-medium text-slate-800 capitalize">{complaint.priority || 'Normal'}</div>
              </div>
            </div>
          </div>

          {/* Progress Timeline */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h2 className="text-lg font-bold text-slate-800 mb-6">Progress Timeline</h2>
            <div className="flex items-center gap-2 w-full max-w-lg mx-auto">
              {['SUBMITTED', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED'].map((step, i, arr) => {
                const status = getStepStatus(step);
                return (
                  <React.Fragment key={step}>
                    <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${
                      status === 'completed' ? 'bg-emerald-500' : status === 'current' ? 'bg-blue-500 ring-4 ring-blue-100' : 'bg-slate-300'
                    }`}>
                      {status === 'completed' && <CheckCircle className="w-5 h-5 text-white" />}
                    </div>
                    {i < arr.length - 1 && (
                      <div className={`flex-1 h-1 rounded-full transition-colors ${
                        status === 'completed' ? 'bg-emerald-500' : 'bg-slate-200'
                      }`} />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
            <div className="flex justify-between w-full max-w-lg mx-auto mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              <span>Submitted</span>
              <span>Assigned</span>
              <span>In Progress</span>
              <span>Resolved</span>
            </div>
          </div>
        </div>

        {/* Right Column - Actions */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-5 sticky top-24">
            <h2 className="text-lg font-bold text-slate-800 border-b border-slate-100 pb-2">Update Resolution</h2>
            
            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-700 block">Change Status</label>
              <select 
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none p-2.5 text-slate-700 font-medium"
              >
                <option value="SUBMITTED">Submitted</option>
                <option value="ASSIGNED">Assigned</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="RESOLVED">Resolved</option>
                <option value="REJECTED">Rejected</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-700 block">Admin Remarks</label>
              <textarea 
                rows="4"
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                placeholder="Add internal notes or resolution remarks..."
                className="w-full bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none p-3 text-slate-700 resize-none text-sm"
              ></textarea>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-700 block">Upload Proof</label>
              <div className="border-2 border-dashed border-slate-200 rounded-xl p-4 text-center hover:bg-slate-50 transition-colors cursor-pointer">
                <Paperclip className="w-5 h-5 text-slate-400 mx-auto mb-1" />
                <span className="text-xs text-slate-500">Click to upload files</span>
              </div>
            </div>

            <button 
              onClick={handleUpdate}
              disabled={updating || newStatus === complaint.status}
              className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl font-bold transition-all duration-200 ${
                updating || newStatus === complaint.status 
                  ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  : 'bg-slate-900 text-white hover:bg-slate-800 shadow-lg hover:shadow-xl hover:-translate-y-0.5 active:scale-[0.98]'
              }`}
            >
              <Save className="w-5 h-5" />
              {updating ? 'Saving...' : 'Save Update'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ComplaintDetail;
