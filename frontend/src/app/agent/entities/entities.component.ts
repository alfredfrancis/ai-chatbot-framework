import { Component, OnInit } from '@angular/core';
import { EntitiesService } from '../../services/entities.service'
@Component({
  selector: 'app-entities',
  templateUrl: './entities.component.html',
  styleUrls: ['./entities.component.scss']
})
export class EntitiesComponent implements OnInit {

  constructor(private entitiesService: EntitiesService) { }

  entities = []

  ngOnInit() {
    this.entitiesService.getEntities().then(
      (result: Array<any>) => {
        this.entities = result
      }
    )
  }

  newEntity(name) {
    this.entitiesService.create_entity({ "name": name }).then(
      (result) => {
        this.entities.push({
          "_id":{
            "$oid":result["_id"]
          },
          "name": name
        })
      }
    )
  }

  deleteEntity(id,i){
    this.entitiesService.delete_entity(id).then(
      ()=>{
        this.entities.splice(i,1)
      }
    )
  }

}
