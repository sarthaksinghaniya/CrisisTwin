import React, { useState, useEffect } from 'react';
import { getOfficerComplaints } from '../../services/api';
import ComplaintTable from '../../components/officer/ComplaintTable';
import FilterBar from '../../components/officer/FilterBar';
import Pagination from '../../components/officer/Pagination';
import Loader from '../../components/Loader';
import { getSocket } from '../../services/socket';
import toast from 'react-hot-toast';

const ComplaintsList = () => {
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [districtFilter, setDistrictFilter] = useState('all');
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  useEffect(() => {
    fetchComplaints();
  }, []);

  // Real-time: auto-refresh when new complaint arrives
  useEffect(() => {
    const socket = getSocket();
    if (!socket) return;

    const handleNewComplaint = (data) => {
      toast.success(`New complaint received: ${data.ticket_id}`);
      fetchComplaints();
    };

    socket.on('newComplaint', handleNewComplaint);
    return () => socket.off('newComplaint', handleNewComplaint);
  }, []);

  const fetchComplaints = async () => {
    try {
      setLoading(true);
      const data = await getOfficerComplaints();
      setComplaints(Array.isArray(data) ? data : data.items || []);
    } catch (error) {
      console.error('Failed to fetch complaints', error);
    } finally {
      setLoading(false);
    }
  };

  // Apply filters
  const filteredComplaints = complaints.filter(c => {
    const matchStatus = statusFilter === 'all' || (c.status || 'pending').toLowerCase() === statusFilter.toLowerCase();
    const matchDistrict = districtFilter === 'all' || (c.district || c.location || '').toLowerCase().includes(districtFilter.toLowerCase());
    return matchStatus && matchDistrict;
  });

  // Apply pagination
  const totalPages = Math.ceil(filteredComplaints.length / itemsPerPage);
  const paginatedComplaints = filteredComplaints.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [statusFilter, districtFilter]);

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Complaints</h1>
        <p className="text-sm text-slate-500 mt-1">Manage and update all assigned grievances</p>
      </div>

      <FilterBar 
        statusFilter={statusFilter} 
        setStatusFilter={setStatusFilter}
        districtFilter={districtFilter}
        setDistrictFilter={setDistrictFilter}
      />

      {loading ? (
        <div className="py-20"><Loader /></div>
      ) : (
        <div className="space-y-4">
          <ComplaintTable complaints={paginatedComplaints} />
          <Pagination 
            currentPage={currentPage} 
            totalPages={totalPages} 
            onPageChange={setCurrentPage} 
          />
        </div>
      )}
    </div>
  );
};

export default ComplaintsList;
