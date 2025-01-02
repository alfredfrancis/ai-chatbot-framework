"use client";

import React, { useState, useEffect, useRef } from 'react';
import { getIntent } from '../../../../services/intents';
import { getTrainingData, saveTrainingData } from '../../../../services/training';
import { getEntities } from '../../../../services/entities';
import './style.css';

interface Entity {
  name: string;
  value: string;
  begin: number;
  end: number;
}

interface Example {
  text: string;
  entities: Entity[];
}

interface SelectionInfo {
  value: string;
  begin: number;
  end: number;
}

const TrainComponent = ({ id }: { id: string }) => {
  const [trainingData, setTrainingData] = useState<Example[]>([]);
  const [newExampleText, setNewExampleText] = useState('');
  const [newEntityName, setNewEntityName] = useState('');
  const [entities, setEntities] = useState<any[]>([]);
  const [intent, setIntent] = useState<any>(null);
  const [selectionInfo, setSelectionInfo] = useState<SelectionInfo>({
    value: '',
    begin: 0,
    end: 0
  });
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [intentData, trainingDataResult, entitiesData] = await Promise.all([
          getIntent(id),
          getTrainingData(id),
          getEntities()
        ]);
        setIntent(intentData);
        setTrainingData(trainingDataResult);
        setEntities(entitiesData);
      } catch (error) {
        console.error('Error fetching data:', error);
        setMessage({ type: 'error', text: 'Failed to load data' });
      }
    };
    fetchData();
  }, [id]);

  const getAnnotatedText = (example: Example) => {
    let text = example.text;
    example.entities.forEach(entity => {
      const key = entity.value;
      text = text.replace(
        new RegExp(key, 'g'),
        `<mark class="entity-highlight">${key}</mark>`
      );
    });
    return text;
  };

  const addNewExample = () => {
    if (!newExampleText.trim()) return;
    setTrainingData(prev => [{
      text: newExampleText,
      entities: []
    }, ...prev]);
    setNewExampleText('');
  };

  const deleteExample = (exampleIndex: number) => {
    setTrainingData(prev => prev.filter((_, index) => index !== exampleIndex));
  };

  const deleteEntity = (exampleIndex: number, entityIndex: number) => {
    setTrainingData(prev => prev.map((example, index) => {
      if (index === exampleIndex) {
        return {
          ...example,
          entities: example.entities.filter((_, eIndex) => eIndex !== entityIndex)
        };
      }
      return example;
    }));
  };

  const snapSelectionToWord = () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return;

    const range = document.createRange();
    range.setStart(sel.anchorNode!, sel.anchorOffset);
    range.setEnd(sel.focusNode!, sel.focusOffset);
    const backwards = range.collapsed;
    range.detach();

    const endNode = sel.focusNode;
    const endOffset = sel.focusOffset;
    sel.collapse(sel.anchorNode, sel.anchorOffset);

    const direction = backwards ? ['backward', 'forward'] : ['forward', 'backward'];
    sel.modify("move", direction[0], "character");
    sel.modify("move", direction[1], "word");
    sel.extend(endNode!, endOffset);
    sel.modify("extend", direction[1], "character");
    sel.modify("extend", direction[0], "word");
  };

  const getSelectionInfo = (): SelectionInfo | null => {
    const selection = window.getSelection();
    if (!selection || selection.anchorOffset === selection.focusOffset) return null;

    const value = selection.toString();
    const begin = Math.min(selection.anchorOffset, selection.focusOffset);
    const end = Math.max(selection.anchorOffset, selection.focusOffset);

    return { value, begin, end };
  };

  const handleAnnotate = () => {
    snapSelectionToWord();
    const info = getSelectionInfo();
    if (info) {
      setSelectionInfo(info);
    }
  };

  const addNewEntity = (exampleIndex: number) => {
    if (!newEntityName || !selectionInfo.value) return;

    setTrainingData(prev => prev.map((example, index) => {
      if (index === exampleIndex) {
        return {
          ...example,
          entities: [...example.entities, {
            value: selectionInfo.value,
            begin: selectionInfo.begin,
            end: selectionInfo.end,
            name: newEntityName
          }]
        };
      }
      return example;
    }));
    setNewEntityName('');
    setSelectionInfo({ value: '', begin: 0, end: 0 });
  };

  const updateTrainingData = async () => {
    try {
      await saveTrainingData(id, trainingData);
      setMessage({ type: 'success', text: 'Training data saved successfully' });
    } catch (error) {
      console.error('Error saving training data:', error);
      setMessage({ type: 'error', text: 'Failed to save training data' });
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-semibold text-gray-800">Train Intent: {intent?.name}</h1>
          <button
            onClick={updateTrainingData}
            className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors duration-200"
          >
            Save Training Data
          </button>
        </div>
        <p className="text-gray-600 mt-1">
          Train your intent for possible user inputs. Tag required parameters using mouse and give them labels.
        </p>
      </div>

      {message && (
        <div className={`p-4 mb-4 rounded-lg ${message.type === 'success' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {message.text}
        </div>
      )}

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex gap-4">
          <input
            type="text"
            value={newExampleText}
            onChange={(e) => setNewExampleText(e.target.value)}
            placeholder="Enter example text here"
            className="flex-1 p-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-green-200 focus:border-green-500"
          />
          <button
            onClick={addNewExample}
            className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors duration-200"
          >
            Add to training set
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {trainingData.map((example, exampleIndex) => (
          <div key={exampleIndex} className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex justify-between items-start mb-4">
              <div
                className="flex-1 p-4 bg-gray-50 rounded-lg"
                dangerouslySetInnerHTML={{ __html: getAnnotatedText(example) }}
              />
              <button
                onClick={() => deleteExample(exampleIndex)}
                className="ml-2 p-2 text-red-500 hover:bg-red-50 rounded-lg"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div
              className="p-4 bg-gray-50 rounded-lg mb-4"
              contentEditable
              onMouseUp={handleAnnotate}
              suppressContentEditableWarning
            >
              {example.text}
            </div>

            <div className="mb-4">
              {selectionInfo.value ? (
                <div className="flex gap-4 items-center">
                  <select
                    value={newEntityName}
                    onChange={(e) => setNewEntityName(e.target.value)}
                    className="p-2 border border-gray-300 rounded-lg"
                  >
                    <option value="">Select entity</option>
                    {entities.map((entity, index) => (
                      <option key={index} value={entity.name}>
                        {entity.name}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => addNewEntity(exampleIndex)}
                    className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors duration-200"
                    disabled={!newEntityName}
                  >
                    Add entity for "{selectionInfo.value}"
                  </button>
                </div>
              ) : (
                <div className="text-gray-500">Select text to add an entity</div>
              )}
            </div>

            <div className="border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left">Entity</th>
                    <th className="px-4 py-2 text-left">Value</th>
                    <th className="px-4 py-2 w-16"></th>
                  </tr>
                </thead>
                <tbody>
                  {example.entities.map((entity, entityIndex) => (
                    <tr key={entityIndex} className="border-t">
                      <td className="px-4 py-2">{entity.name}</td>
                      <td className="px-4 py-2">{entity.value}</td>
                      <td className="px-4 py-2">
                        <button
                          onClick={() => deleteEntity(exampleIndex, entityIndex)}
                          className="p-1 text-red-500 hover:bg-red-50 rounded"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TrainComponent; 