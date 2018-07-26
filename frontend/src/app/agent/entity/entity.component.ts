import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Params, Router } from '@angular/router';
import { EntitiesService } from '../../services/entities.service'

import {MatChipInputEvent} from '@angular/material';
import {ENTER, COMMA} from '@angular/cdk/keycodes';

@Component({
  selector: 'app-entity',
  templateUrl: './entity.component.html',
  styleUrls: ['./entity.component.scss']
})
export class EntityComponent implements OnInit {
  
  constructor(private entitiesService: EntitiesService,private _activatedRoute: ActivatedRoute) { }

  separatorKeysCodes = [ENTER, COMMA];
  entity;
  ngOnInit() {

    this._activatedRoute.data
    .subscribe((data:{entity:any}) => {
      console.log("selected entity =>>",data.entity)
      this.entity = data.entity
  });   

  }
  newValue(value){
    this.entity["entity_values"].push({
      "value":value,
      "synonyms":[]
    })
  }

  add(value_index,event: MatChipInputEvent): void {
    let input = event.input;
    let value = event.value;

    // Add our fruit
    if ((value || '').trim()) {
      this.entity.entity_values[value_index].synonyms.push(value);
    }

    // Reset the input value
    if (input) {
      input.value = '';
    }
  }

  remove_synonym(value_index,synonym_index): void {

    if (synonym_index >= 0) {
      this.entity.entity_values[value_index].synonyms.splice(synonym_index, 1);
    }
  }
  saveEntity(){
    this.entitiesService.saveEntity(this.entity).then(
      (result:any)=>{
        console.log("Success: " + JSON.stringify(result));
      }
    )
  }
  deleteEntityValue(value_index){
    this.entity["entity_values"].splice(value_index,1);
  }
}
