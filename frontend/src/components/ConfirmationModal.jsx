import React, { useState, useEffect } from "react";

export default function ConfirmationModal({ action, onConfirm, onDecline }) {
  const [params, setParams] = useState({});

  useEffect(() => {
    if (action && action.parameters) {
      setParams({ ...action.parameters });
    }
  }, [action]);

  if (!action) return null;

  const handleChange = (key, val) => {
    setParams(prev => ({ ...prev, [key]: val }));
  };

  const handleConfirm = () => {
    onConfirm(params);
  };

  return (
    <div className="confirm-modal-overlay">
      <div className="confirm-modal">
        <div className="confirm-header">
          <span className="confirm-icon">🔔</span>
          <h3>Confirm & Edit Action</h3>
        </div>
        <div className="confirm-body">
          <div className="confirm-type">{action.action_type.toUpperCase()}</div>
          <p className="confirm-desc">Review and edit the details below before confirming:</p>
          
          <div className="confirm-params">
            {Object.entries(params)
              .filter(([k]) => !["user_id", "project_id"].includes(k)) // Don't edit internal IDs
              .map(([k, v]) => (
                <div key={k} className="param-row-edit">
                  <label className="param-label">{k.replace(/_/g, " ")}</label>
                  {k === "description" ? (
                    <textarea 
                      className="param-input"
                      value={v || ""} 
                      onChange={(e) => handleChange(k, e.target.value)}
                    />
                  ) : (
                    <input 
                      type="text" 
                      className="param-input"
                      value={v || ""} 
                      onChange={(e) => handleChange(k, e.target.value)}
                    />
                  )}
                </div>
              ))}
              
            {params.project_id && (
               <div className="param-row-static">
                  <span className="param-label">Project ID</span>
                  <span className="param-val-static">{params.project_id}</span>
               </div>
            )}
          </div>
        </div>
        <div className="confirm-actions">
          <button className="btn-decline" onClick={onDecline} id="decline-btn">Cancel</button>
          <button className="btn-confirm" onClick={handleConfirm} id="confirm-btn">Confirm</button>
        </div>
      </div>
    </div>
  );
}
