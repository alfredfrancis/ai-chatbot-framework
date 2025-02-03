"use client";

import React, { useState, useEffect } from 'react';
import { getIntent } from '../../../../services/intents';
import { getTrainingData, saveTrainingData,EntityModel, IntentModel } from '../../../../services/training';
import { getEntities } from '../../../../services/entities';
import { useSnackbar } from '../../../../components/Snackbar/SnackbarContext';
import { Popover } from 'flowbite-react';
import { QuestionMarkCircleIcon } from '@heroicons/react/24/outline';
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

type PageProps = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default function TrainPage({ params }: PageProps) {
  const { id } = React.use(params);
  const { addSnackbar } = useSnackbar();
  const [trainingData, setTrainingData] = useState<Example[]>([]);
  const [newExampleText, setNewExampleText] = useState('');
  const [newEntityName, setNewEntityName] = useState('');
  const [entities, setEntities] = useState<EntityModel[]>([]);
  const [intent, setIntent] = useState<IntentModel>({ name: '',intentId: '', parameters: [], speechResponse: '', apiTrigger: false });
  const [selectionInfo, setSelectionInfo] = useState<SelectionInfo>({
    value: '',
    begin: 0,
    end: 0
  });
  const [activeExampleIndex, setActiveExampleIndex] = useState<number | null>(null);

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
        addSnackbar('Failed to load training data', 'error');
      }
    };
    fetchData();
  }, [id, addSnackbar]);

  const handleTextChange = (exampleIndex: number, event: React.FormEvent<HTMLDivElement>) => {
    const selection = window.getSelection();
    const cursorPosition = selection?.focusOffset || 0;
    const node = selection?.focusNode;

    const newText = event.currentTarget.textContent || '';
    setTrainingData(prev => prev.map((example, index) => {
      if (index === exampleIndex) {
        return {
          ...example,
          text: newText,
          entities: example.entities.filter(entity => {
            // Keep entities that are still within the text bounds
            return entity.begin <= newText.length && entity.end <= newText.length;
          })
        };
      }
      return example;
    }));

    // Restore cursor position after React re-render
    requestAnimationFrame(() => {
      if (selection && node?.parentElement) {
        const range = document.createRange();
        range.setStart(node, cursorPosition);
        range.collapse(true);
        selection.removeAllRanges();
        selection.addRange(range);
      }
    });
  };

  const renderTrainingText = (example: Example) => {
    if (!example.entities.length) {
      return example.text;
    }

    const result = [];
    let lastIndex = 0;
    
    // Sort entities by begin position to ensure correct order
    const sortedEntities = [...example.entities].sort((a, b) => a.begin - b.begin);
    
    for (const entity of sortedEntities) {
      // Add text before the entity
      if (entity.begin > lastIndex) {
        result.push(example.text.substring(lastIndex, entity.begin));
      }
      
      // Add the entity
      result.push(
        <mark key={`${entity.begin}-${entity.end}`} className="entity-highlight">
          {entity.value}
        </mark>
      );
      
      lastIndex = entity.end;
    }
    
    // Add remaining text
    if (lastIndex < example.text.length) {
      result.push(example.text.substring(lastIndex));
    }
    
    return result;
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

  const handleAnnotate = (exampleIndex: number) => {
    snapSelectionToWord();
    const info = getSelectionInfo();
    if (info) {
      setSelectionInfo(info);
      setActiveExampleIndex(exampleIndex);
    } else {
      setActiveExampleIndex(null);
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
    setActiveExampleIndex(null);
  };

  const updateTrainingData = async () => {
    try {
      await saveTrainingData(id, trainingData);
      addSnackbar('Training data saved successfully', 'success');
    } catch (error) {
      console.error('Error saving training data:', error);
      addSnackbar('Failed to save training data', 'error');
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
        <div className="flex items-center gap-2 mt-1">
          <p className="text-gray-600">
            Train your intent for possible user inputs.
          </p>
          <Popover 
            content={
              <div className="max-w-sm space-y-2 p-3 bg-gray-50 rounded-lg">
                <p>
                  To add entity annotations:
                </p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>Select the text you want to annotate</li>
                  <li>Choose an entity type from the dropdown</li>
                  <li>Click the "Add Entity" button</li>
                </ul>
              </div>
            }
          >
            <QuestionMarkCircleIcon className="h-5 w-5 text-gray-400 hover:text-gray-500 cursor-help" />
          </Popover>
        </div>
      </div>

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
                className="flex-1 p-4 bg-gray-50 rounded-lg training-text"
                contentEditable
                onMouseUp={() => handleAnnotate(exampleIndex)}
                onInput={(e) => handleTextChange(exampleIndex, e)}
                suppressContentEditableWarning
              >
                {renderTrainingText(example)}
              </div>
              <button
                onClick={() => deleteExample(exampleIndex)}
                className="ml-2 p-2 text-red-500 hover:bg-red-50 rounded-lg"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="mb-4">
              {activeExampleIndex === exampleIndex && selectionInfo.value && (
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
                  >
                    Add Entity
                  </button>
                </div>
              )}
                {example.entities.length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-medium text-gray-700 mb-2">Tagged Entities:</h4>
                    <div className="space-y-2">
                      {example.entities.map((entity, entityIndex) => (
                        <div key={entityIndex} className="flex items-center gap-2">
                          <span className="px-2 py-1 bg-green-100 text-green-800 rounded">
                            {entity.name}: {entity.value}
                          </span>
                          <button
                            onClick={() => deleteEntity(exampleIndex, entityIndex)}
                            className="p-1 text-red-500 hover:bg-red-50 rounded"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
} 