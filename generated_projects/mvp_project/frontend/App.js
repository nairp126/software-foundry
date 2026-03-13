import React, { useState, useEffect } from 'react';
import TodoForm from './TodoForm';
import TodoList from './TodoList';

function App() {
  const [todos, setTodos] = useState([]);

  useEffect(() => {
    fetch('/todos')
      .then(response => response.json())
      .then(data => setTodos(data));
  }, []);

  const addTodo = (todo) => {
    fetch('/todos', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(todo)
    })
    .then(response => response.json())
    .then(newTodo => setTodos([...todos, newTodo]));
  };

  const updateTodo = (id, updatedTodo) => {
    fetch(`/todos/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updatedTodo)
    })
    .then(response => response.json())
    .then(updatedTodo => setTodos(todos.map(todo => todo.id === id ? updatedTodo : todo)));
  };

  const deleteTodo = (id) => {
    fetch(`/todos/${id}`, {
      method: 'DELETE'
    })
    .then(() => setTodos(todos.filter(todo => todo.id !== id)));
  };

  return (
    <div>
      <h1>Simple Todo App</h1>
      <TodoForm onSubmit={addTodo} />
      <TodoList todos={todos} onUpdate={updateTodo} onDelete={deleteTodo} />
    </div>
  );
}

export default App;