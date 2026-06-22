import React, { useState } from 'react';
import { useSubmitComplaint } from '../services/queries';
import { FileText, ArrowRight, CheckCircle2, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import AnimatedPage from '../components/AnimatedPage';
import { useAuth } from '../context/AuthContext';

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
};

const itemVariants = {
  hidden: { opacity: 0, x: -15 },
  show: { opacity: 1, x: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
};

const Home = () => {
  const [formData, setFormData] = useState({ title: '', description: '', district: '', department: '', phone: '' });
  const [successData, setSuccessData] = useState(null);
  const [localError, setLocalError] = useState(null);
  const { user } = useAuth();

  const { mutateAsync: submitComplaint, isPending: loading } = useSubmitComplaint();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError(null);
    
    const submissionData = new FormData();
    submissionData.append('citizen_name', user?.name || 'Delhi Citizen');
    submissionData.append('citizen_email', user?.email || 'citizen@example.com');
    submissionData.append('citizen_phone', formData.phone);
    submissionData.append('title', formData.title);
    submissionData.append('description', formData.description);
    submissionData.append('district', formData.district);
    submissionData.append('category', formData.department);

    try {
      const res = await submitComplaint(submissionData);
      setSuccessData(res);
      setFormData({ title: '', description: '', district: '', department: '', phone: '' });
    } catch (error) {
      // The error message is automatically parsed by our Axios interceptor!
      setLocalError(error.message || 'Failed to submit complaint. Please try again.');
    }
  };

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  return (
    <AnimatedPage className="relative min-h-[85vh] flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      {/* Background ambient gradients */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none -z-10">
        <motion.div 
          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0.8, 0.5] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-[10%] -left-[10%] w-[40%] h-[40%] rounded-full bg-blue-400/20 blur-[120px]" 
        />
        <motion.div 
          animate={{ scale: [1, 1.3, 1], opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 2 }}
          className="absolute bottom-[10%] -right-[10%] w-[30%] h-[40%] rounded-full bg-indigo-400/20 blur-[120px]" 
        />
      </div>

      <div className="w-full max-w-2xl mx-auto space-y-8">
        
        {/* Header Section */}
        <div className="text-center space-y-4">
          <motion.div 
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200, damping: 20 }}
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-slate-100 to-white text-slate-600 mb-2 shadow-sm border border-white/50 backdrop-blur-sm"
          >
            <FileText className="w-8 h-8" />
          </motion.div>
          <h1 className="text-4xl md:text-5xl font-extrabold text-slate-800 tracking-tight">
            File a <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Complaint</span>
          </h1>
          <p className="text-lg text-slate-500 font-medium">
            We're here to help. Please provide details about your issue.
          </p>
        </div>

        {/* Main Form Card */}
        <motion.div 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="relative bg-white/60 backdrop-blur-xl border border-white/80 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-3xl p-8 md:p-10 overflow-hidden"
        >
          {localError && (
            <div className="mb-6 bg-rose-50/90 backdrop-blur-sm text-rose-600 p-4 rounded-xl text-center font-medium border border-rose-100 flex items-center justify-center gap-2 shadow-sm">
              <AlertCircle className="w-5 h-5" />
              {localError}
            </div>
          )}

          <AnimatePresence mode="wait">
            {successData ? (
              <motion.div 
                key="success"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ type: "spring", stiffness: 200, damping: 20 }}
                className="text-center py-8 space-y-6"
              >
                <motion.div 
                  initial={{ scale: 0 }} 
                  animate={{ scale: 1 }} 
                  transition={{ type: "spring", delay: 0.2 }}
                  className="mx-auto w-24 h-24 bg-gradient-to-tr from-emerald-100 to-teal-50 rounded-full flex items-center justify-center text-emerald-500 shadow-sm border border-white/50"
                >
                  <CheckCircle2 className="w-12 h-12" />
                </motion.div>
                <div>
                  <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight">Complaint Submitted!</h2>
                  <p className="text-slate-500 mt-2 font-medium">Your complaint has been successfully registered.</p>
                </div>
                
                <div className="bg-white p-6 rounded-2xl border border-slate-200/60 shadow-sm inline-block w-full max-w-sm mt-4">
                  <p className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">Your Ticket ID</p>
                  <p className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">{successData.ticket_id}</p>
                  <p className="text-xs text-slate-400 mt-2">Please save this ID to track your complaint status.</p>
                </div>

                <button 
                  onClick={() => setSuccessData(null)} 
                  className="mt-8 w-full py-4 px-4 bg-slate-900 text-white font-bold rounded-xl shadow-lg hover:shadow-xl hover:-translate-y-0.5 hover:bg-slate-800 transition-all duration-300 active:scale-[0.98]"
                >
                  Submit Another Complaint
                </button>
              </motion.div>
            ) : (
              <motion.form 
                key="form"
                variants={containerVariants}
                initial="hidden"
                animate="show"
                exit={{ opacity: 0 }}
                onSubmit={handleSubmit} 
                className="space-y-6"
              >
                <motion.div variants={itemVariants} className="space-y-1.5 group">
                  <label className="text-sm font-semibold text-slate-700 ml-1 group-focus-within:text-blue-600 transition-colors">Complaint Title</label>
                  <input
                    type="text"
                    name="title"
                    required
                    placeholder="Brief summary of the issue"
                    value={formData.title}
                    onChange={handleChange}
                    className="w-full px-4 py-3.5 bg-white/80 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all duration-300 shadow-sm hover:bg-white placeholder:text-slate-400 font-medium text-slate-800"
                  />
                </motion.div>

                <motion.div variants={itemVariants} className="space-y-1.5 group">
                  <label className="text-sm font-semibold text-slate-700 ml-1 group-focus-within:text-blue-600 transition-colors">Contact Phone Number</label>
                  <input
                    type="tel"
                    name="phone"
                    required
                    placeholder="Enter your 10-15 digit phone number (e.g., 9999999999)"
                    value={formData.phone}
                    onChange={handleChange}
                    className="w-full px-4 py-3.5 bg-white/80 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all duration-300 shadow-sm hover:bg-white placeholder:text-slate-400 font-medium text-slate-800"
                  />
                </motion.div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <motion.div variants={itemVariants} className="space-y-1.5 group">
                    <label className="text-sm font-semibold text-slate-700 ml-1 group-focus-within:text-blue-600 transition-colors">District / Location</label>
                    <input
                      type="text"
                      name="district"
                      required
                      placeholder="e.g., Downtown"
                      value={formData.district}
                      onChange={handleChange}
                      className="w-full px-4 py-3.5 bg-white/80 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all duration-300 shadow-sm hover:bg-white placeholder:text-slate-400 font-medium text-slate-800"
                    />
                  </motion.div>

                  <motion.div variants={itemVariants} className="space-y-1.5 group">
                    <label className="text-sm font-semibold text-slate-700 ml-1 group-focus-within:text-blue-600 transition-colors">Department</label>
                    <select
                      name="department"
                      required
                      value={formData.department}
                      onChange={handleChange}
                      className="w-full px-4 py-3.5 bg-white/80 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all duration-300 shadow-sm hover:bg-white text-slate-800 font-medium appearance-none"
                    >
                      <option value="" disabled className="text-slate-400">Select department</option>
                      <option value="Water">Water Supply</option>
                      <option value="Electricity">Electricity</option>
                      <option value="Roads">Roads & Transport</option>
                      <option value="Sanitation">Sanitation</option>
                      <option value="Other">Other</option>
                    </select>
                  </motion.div>
                </div>

                <motion.div variants={itemVariants} className="space-y-1.5 group">
                  <label className="text-sm font-semibold text-slate-700 ml-1 group-focus-within:text-blue-600 transition-colors">Detailed Description</label>
                  <textarea
                    name="description"
                    required
                    rows="4"
                    placeholder="Please provide as much detail as possible..."
                    value={formData.description}
                    onChange={handleChange}
                    className="w-full px-4 py-3.5 bg-white/80 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all duration-300 shadow-sm hover:bg-white placeholder:text-slate-400 font-medium text-slate-800 resize-none"
                  ></textarea>
                </motion.div>

                <motion.button 
                  variants={itemVariants}
                  whileTap={{ scale: loading ? 1 : 0.98 }}
                  type="submit" 
                  disabled={loading}
                  className={`group w-full flex items-center justify-center gap-2 py-4 mt-8 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-lg font-bold rounded-xl shadow-lg shadow-blue-500/25 transition-all duration-300 ${loading ? 'opacity-70 cursor-not-allowed' : 'hover:shadow-xl hover:shadow-blue-500/40 hover:-translate-y-0.5'}`}
                >
                  {loading ? (
                    <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>
                      Submit Complaint
                      <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform duration-300 opacity-90" />
                    </>
                  )}
                </motion.button>
              </motion.form>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </AnimatedPage>
  );
};

export default Home;
